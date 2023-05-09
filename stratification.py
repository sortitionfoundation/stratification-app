"""
Python (3) script to do a stratified, random selection from respondents to random mail out

Copyright (C) 2019-2023 Brett Hennig bsh [AT] sortitionfoundation.org & Paul Gölz goelz (AT) seas.harvard.edu

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public
License as published by the Free Software Foundation; either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program; if not, see
<https://www.gnu.org/licenses>.

Additional permission under GNU GPL version 3 section 7

If you modify this Program, or any covered work, by linking or combining it with Gurobi (or a modified version of that
library), containing parts covered by the terms of GUROBI OPTIMIZATION, LLC END-USER LICENSE AGREEMENT, the licensors of
this Program grant you additional permission to convey the resulting work.
"""
import codecs
import copy
import csv
import random
import typing
from copy import deepcopy
from io import StringIO
from math import log
from pathlib import Path
from typing import Any, Dict, List, Tuple, FrozenSet, Iterable, Optional, Set

import cvxpy as cp
# For how to use gspread see:
# https://www.analyticsvidhya.com/blog/2020/07/read-and-update-google-spreadsheets-with-python/
# and:
#	 https://github.com/burnash/gspread
#	 https://gspread.readthedocs.io/en/latest/
#	 https://gspread.readthedocs.io/en/latest/api.html
import gspread
import mip
import numpy as np
import toml
from oauth2client.service_account import ServiceAccountCredentials

# 0 means no debug message, higher number (could) mean more messages
debug = 0
# numerical deviation accepted as equality when dealing with solvers
EPS = 0.0005  # TODO: Find good value
EPS_NASH = 0.1
EPS2 = 0.00000001

DEFAULT_SETTINGS = """
# #####################################################################
#
# IF YOU EDIT THIS FILE YOU NEED TO RESTART THE APPLICATION
#
# #####################################################################

# this is written in TOML - https://github.com/toml-lang/toml

# this is the name of the (unique) field for each person
id_column = "nationbuilder_id"

# if check_same_address is true, then no 2 people from the same address will be selected
# the comparison checks if the TWO fields listed here are the same for any person
check_same_address = true
check_same_address_columns = [
    "primary_address1",
    "zip_royal_mail"
]

max_attempts = 100
columns_to_keep = [
    "first_name",
    "last_name",
    "mobile_number",
    "email",
    "primary_address1",
    "primary_address2",
    "primary_city",
    "zip_royal_mail",
    "tag_list",
    "age",
    "gender"
]

# selection_algorithm can either be "legacy", "maximin", "leximin", or "nash"
selection_algorithm = "leximin"

# random number seed - if this is NOT zero then it is used to set the random number generator seed
random_number_seed = 0
"""


class NoSettingsFile(Exception):
    pass


class Settings:
    def __init__(self, id_column, columns_to_keep, check_same_address, check_same_address_columns, max_attempts,
                 selection_algorithm, random_number_seed, json_file_path):
        try:
            assert (isinstance(id_column, str))
            assert (isinstance(columns_to_keep, list))
            # if they have no personal data this could actually be empty
            # assert(len(columns_to_keep) > 0)
            for column in columns_to_keep:
                assert (isinstance(column, str))
            assert (isinstance(check_same_address, bool))
            assert (isinstance(check_same_address_columns, list))
            # this could be empty
            assert (len(check_same_address_columns) == 2 or len(check_same_address_columns) == 0)
            for column in check_same_address_columns:
                assert (isinstance(column, str))
            assert (isinstance(max_attempts, int))
            assert (isinstance(random_number_seed, int))
            assert (selection_algorithm in ["legacy", "maximin", "nash"])
        except AssertionError as error:
            print(error)

        self.id_column = id_column
        self.columns_to_keep = columns_to_keep
        self.check_same_address = check_same_address
        self.check_same_address_columns = check_same_address_columns
        self.max_attempts = max_attempts
        self.selection_algorithm = selection_algorithm
        self.random_number_seed = random_number_seed
        self.json_file_path = json_file_path

    @classmethod
    def load_from_file(cls):
        message = ""
        settings_file_path = Path.home() / "sf_stratification_settings.toml"
        if not settings_file_path.is_file():
            with open(settings_file_path, "w", encoding='utf-8') as settings_file:
                settings_file.write(DEFAULT_SETTINGS)
            message = "Wrote default settings to '{}' - if editing is required, restart this app.".format(
                settings_file_path.absolute()
            )
        with open(settings_file_path, "r", encoding='utf-8') as settings_file:
            settings = toml.load(settings_file)
        # you can't check an address if there is no info about which columns to check...
        if settings['check_same_address'] == False:
            message += "<b>WARNING</b>: Settings file is such that we do NOT check if respondents have same address."
            settings['check_same_address_columns'] = []
        if len(settings['check_same_address_columns']) == 0 and settings['check_same_address'] == True:
            message += "\n<b>ERROR</b>: in sf_stratification_settings.toml file check_same_address is TRUE but there are no columns listed to check! FIX THIS and RESTART this program!"
        settings['json_file_path'] = Path.home() / "secret_do_not_commit.json"
        return cls(
            settings['id_column'],
            settings['columns_to_keep'],
            settings['check_same_address'],
            settings['check_same_address_columns'],
            settings['max_attempts'],
            settings['selection_algorithm'],
            settings['random_number_seed'],
            settings['json_file_path']
        ), message


# class for throwing error/fail exceptions
class SelectionError(Exception):
    def __init__(self, message):
        self.msg = message


###################################
#
# The PeopleAndCats classes below hold all the people and category info sourced from (and written to) the relevant place
#
# categories is a dict of dicts of dicts... like:
#   categories = { 'gender' : gender, 'age' : age, 'geo' : geo, 'socio' : socio }
# with each category a dict of possible values with set data, like:
#     gender = { 'Gender: Male' : { 'min' : 20, 'max' : 24, 'selected' : 0, 'remaining' : 0 },
#                'Gender: Female' : { 'min' : 21, 'max' : 25, 'selected' : 0, 'remaining' : 0 }
# etc         }
#
# Note that there are now optional extra fields in the above: min_flex and max_flex...
#
###################################

class PeopleAndCats():
    # Warning: all / most of these values are hardcoded also somewhere below :-)
    category_file_field_names = ["category", "name", "min", "max", "min_flex", "max_flex"]

    def __init__(self):
        # mins and maxs (from category data) for number of people one can select
        # min_flex and max_flex are how much we are happy for this to "stretch"...
        self.min_max_people = {}
        self.original_categories = None
        self.categories_after_people = None
        self.category_content_loaded = False
        self.people_content_loaded = False
        # this is the main data structure where all the info about the people are kept,
        # including columns to keep, same address column data and category data
        # i.e. everything we need to track for these people!
        self.people = None
        self.columns_data = None
        # after selection, this is just "number_selections" lists of people IDs
        self.people_selected = None
        self.number_people_to_select = 0
        self.number_selections = 1  # default to 1 - why not?
        # these, and the two functions below, are the only annoying things needed to distinguish CSV in GUI..
        self.enable_file_download = False
        self.gen_rem_tab = ''

    def get_selected_file(self):
        return None

    def get_remaining_file(self):
        return None

    # read in stratified selection categories and values - a dict of dicts of dicts...
    def _read_in_cats(self, cat_head, cat_body):
        self.original_categories = {}
        msg = []
        min_val = 0
        max_val = 0
        # to keep track of number in cats - number people selected MUST be between these limits in every cat...
        self.min_max_people = {}
        # check that the fieldnames are (at least) what we expect, and only once,
        # BUT (for reverse compatibility) let min_flex and max_flex be optional
        cat_flex = False
        try:
            if cat_head.count("min_flex") == 1 and cat_head.count("max_flex") == 1:
                cat_flex = True
            for fn in PeopleAndCats.category_file_field_names:
                cat_head_fn_count = cat_head.count(fn)
                if cat_head_fn_count == 0 and (fn != "min_flex" and fn != "max_flex"):
                    raise Exception(
                        "Did not find required column name '{}' in the input ".format(fn)
                    )
                elif cat_head_fn_count > 1:
                    raise Exception(
                        "Found MORE THAN 1 column named '{}' in the input (found {}) ".format(fn, cat_head_fn_count)
                    )
            for row in cat_body:
                # allow for some dirty data - at least strip white space from cat and name
                # but only if they are strings! (sometimes people use ints as cat names or values and then strip produces an exception...)
                cat = row["category"]
                # and skip over any blank lines...
                if cat == '':
                    continue
                if isinstance(cat, str):
                    cat = cat.strip()
                # check for blank entries and report a meaningful error
                cat_value = row["name"]
                if cat_value == '' or row["min"] == '' or row["max"] == '':
                    raise Exception(
                        "ERROR reading in category file: found a blank cell in a row of the category: {}. ".format(cat)
                    )
                if isinstance(cat_value, str):
                    cat_value = cat_value.strip()
                # must convert min/max to ints
                cat_min = int(row["min"])
                cat_max = int(row["max"])
                if cat_flex:
                    if row["min_flex"] == '' or row["max_flex"] == '':
                        raise Exception(
                            "ERROR reading in category file: found a blank min_flex or max_flex cell in a category value: {}. ".format(
                                cat_value)
                        )
                    cat_min_flex = int(row["min_flex"])
                    cat_max_flex = int(row["max_flex"])
                    # if these values exist they must be at least this...
                    if cat_min_flex > cat_min or cat_max_flex < cat_max:
                        raise Exception(
                            "Inconsistent numbers in min_flex and max_flex in the categories input for {}: the flex values must be equal or outside the max and min values. ".format(
                                cat_value)
                        )
                else:
                    cat_min_flex = 0
                    # since we don't know self.number_people_to_select yet! We correct this below
                    cat_max_flex = -1
                if cat in self.original_categories:
                    self.min_max_people[cat]["min"] += cat_min
                    self.min_max_people[cat]["max"] += cat_max
                    self.original_categories[cat].update(
                        {
                            str(cat_value): {  ###forcing this to be a string
                                "min": cat_min,
                                "max": cat_max,
                                "selected": 0,
                                "remaining": 0,
                                "min_flex": cat_min_flex,
                                "max_flex": cat_max_flex,
                            }
                        }
                    )
                else:
                    self.min_max_people.update(
                        {
                            cat: {
                                "min": cat_min,
                                "max": cat_max
                            }
                        }
                    )
                    self.original_categories.update(
                        {
                            cat: {
                                str(cat_value): {  ###forcing this to be a string
                                    "min": cat_min,
                                    "max": cat_max,
                                    "selected": 0,
                                    "remaining": 0,
                                    "min_flex": cat_min_flex,
                                    "max_flex": cat_max_flex,
                                }
                            }
                        }
                    )

            msg += ["Number of categories: {}".format(len(self.original_categories.keys()))]

            # work out what the min and max number of people should be,
            # given these cats
            max_values = [v['max'] for v in self.min_max_people.values()]
            max_val = min(max_values)
            # to avoid errors, if max_flex is not set we must set it at least as high as the highest
            max_flex_val = max(max_values)
            min_values = [v['min'] for v in self.min_max_people.values()]
            min_val = max(min_values)
            # if the min is bigger than the max we're in trouble i.e. there's an input error
            if min_val > max_val:
                raise Exception(
                    "Inconsistent numbers in min and max in the categories input: the sum of the minimum values of a category is larger than the sum of the maximum values of a(nother) category. "
                )

            # check cat_flex to see if we need to set the max here
            # this is only used if these (optional) flex values are NOT given
            for cat_values in self.original_categories.values():
                for cat_value in cat_values.values():
                    if cat_value["max_flex"] == -1:
                        # this must be bigger than the largest max - and could even be more than number of people
                        cat_value[
                            "max_flex"] = max_flex_val

        except Exception as error:
            msg += ["Error loading categories: {}".format(error)]
        return msg, min_val, max_val

    # simple helper function to tidy the code below
    def _check_columns_exist_or_multiple(self, people_head, column_list, error_text):
        for column in column_list:
            column_count = people_head.count(column)
            if column_count == 0:
                raise Exception(
                    "No '{}' column {} found in people data!".format(column, error_text)
                )
            elif column_count > 1:
                raise Exception(
                    "MORE THAN 1 '{}' column {} found in people data!".format(column, error_text)
                )

    # read in people and calculate how many people in each category in database
    def _init_categories_people(self, people_head, people_body, settings: Settings):
        people = {}
        columns_data = {}
        # this modifies the categories, so we keep the original categories here
        self.categories_after_people = deepcopy(self.original_categories)
        categories = self.categories_after_people
        # check that id_column and all the categories, columns_to_keep and check_same_address_columns are in
        # the people data fields...
        msg = []
        try:
            # check both for existence and duplicate column names
            self._check_columns_exist_or_multiple(people_head, [settings.id_column], "(unique id)")
            self._check_columns_exist_or_multiple(people_head, categories.keys(), "(a category)")
            self._check_columns_exist_or_multiple(people_head, settings.columns_to_keep, "(to keep)")
            self._check_columns_exist_or_multiple(people_head, settings.check_same_address_columns, "(to check same address)")
            # let's just merge the check_same_address_columns into columns_to_keep in case they aren't in both
            for col in settings.check_same_address_columns:
                if col not in settings.columns_to_keep:
                    settings.columns_to_keep.append(col)
            for row in people_body:
                pkey = row[settings.id_column]
                # skip over any blank lines... but warn the user
                if pkey == '':
                    msg += ["<b>WARNING</b>: blank cell found in ID column - skipped that line!"]
                    continue
                value = {}
                # get the category values: these are the most important and we must check them
                for cat_key, cats in categories.items():
                    # check for input errors here - if it's not in the list of category values...
                    # allow for some unclean data - at least strip empty space, but only if a str!
                    # (some values will can be numbers)
                    p_value = row[cat_key]
                    if isinstance(row[cat_key], str):
                        p_value = p_value.strip()
                    if p_value not in cats:
                        raise Exception(
                            "ERROR reading in people (init_categories_people): Person (id = {}) has value '{}' not in category {}".format(
                                pkey, p_value, cat_key)
                        )
                    value.update({cat_key: p_value})
                    categories[cat_key][p_value]["remaining"] += 1
                # then get the other column values we need
                # this is address, name etc that we need to keep for output file
                # we don't check anything here - it's just for user convenience
                col_value = {}
                for col in settings.columns_to_keep:
                    value.update({col: row[col]})
                    col_value.update({col: row[col]})
                # add all the data to our people object
                people.update({pkey: value})
                columns_data.update({pkey: col_value})
            # check if any cat[max] is set to zero... if so delete everyone with that cat...
            # NOT DONE: could then check if anyone is left...
            total_num_people = len(people.keys())
            msg += ["Number of people: {}.".format(total_num_people)]
            total_num_deleted = 0
            for cat_key, cats in categories.items():
                for cat, cat_item in cats.items():
                    if cat_item["max"] == 0:  # we don't want any of these people
                        # pass the message in as deleting them might throw an exception
                        msg += ["Category {} full - deleting people...".format(cat)]
                        num_deleted, num_left = delete_all_in_cat(categories, people, cat_key, cat)
                        # if no expcetion was thrown above add this bit to the end of the previous message
                        msg[-1] += " Deleted {}, {} left.".format(num_deleted, num_left)
                        total_num_deleted += num_deleted
            # if the total number of people deleted is lots then we're probably doing a replacement selection, which means
            # the 'remaining' file will be useless - remind the user of this!
            if total_num_deleted > total_num_people / 2:
                msg += [
                    ">>> WARNING <<< That deleted MANY PEOPLE - are you doing a replacement? If so your REMAINING FILE WILL BE USELESS!!!"]
            self.people = people
            self.columns_data = columns_data
        except Exception as error:
            self.people_content_loaded = False
            msg += ["Error loading people: {}".format(error)]
        return msg

    def people_cats_run_stratification(self, settings: Settings, test_selection):
        # if this is being called again (the user hit the button again!) we want to make sure all data is cleared etc
        # but the function called here makes deep copies of categories_after_people and people
        self.people_selected = None
        success, self.people_selected, output_lines = run_stratification(
            self.categories_after_people, self.people, self.columns_data, self.number_people_to_select,
            self.min_max_people, settings, test_selection, self.number_selections
        )
        if success:
            # this also outputs them...
            output_lines += self._get_selected_people_lists(settings)
        return success, output_lines

    # this also outputs them by calling the appropriate derived class method...
    # currently this DOES NOT WORK if self.number_selections > 1 ...
    def _get_selected_people_lists(self, settings: Settings):
        people_working = copy.deepcopy(self.people)
        people_selected = self.people_selected
        output_lines = []

        # if we are doing a multiple selection (only possible from G-sheet at the moment) just spit out selected as is
        # and no remaining tab
        assert (len(people_selected) == self.number_selections)
        if self.number_selections > 1:
            # people_selected should be list of frozensets...
            people_selected_header_row = []
            for index in range(self.number_selections):
                people_selected_header_row += ["Assembly {}".format(index + 1)]
            #people_selected_rows = [people_selected_header_row]
            # initialise an empty 2d list - yes, not pythonic...
            people_selected_rows = [[''] * self.number_selections for i in range(self.number_people_to_select)]
            people_remaining_rows = [[]]
            # put all the assemblies in columns of the output
            for set_count, fset in enumerate(people_selected):
                for p_count, pkey in enumerate(fset):
                    people_selected_rows[p_count][set_count] = pkey
            # there must be some pythonic way to do this but i don't know it...
            #people_selected_rows = [[people_selected[i][j] for i in range(self.number_selections)] for j in range(self.number_people_to_select)]
            # prepend the header row afterwards
            people_selected_rows.insert(0, people_selected_header_row )
            self._output_selected_remaining(settings, people_selected_rows, people_remaining_rows)
        else: # self.number_selections == 1
            categories = self.categories_after_people
            #columns_data = self.columns_data

            # columns_to_keep ALSO contains check_same_address_columns
            people_selected_rows = [[settings.id_column] + settings.columns_to_keep + list(categories.keys())]
            people_remaining_rows = [[settings.id_column] + settings.columns_to_keep + list(categories.keys())]

            num_same_address_deleted = 0
            for pkey in people_selected[0]:
                row = [pkey]
                # this is also just all in here, but in an unordered mess...
                # row += people_working[pkey].values()
                for col in settings.columns_to_keep:
                    row.append(people_working[pkey][col])
                for cat_key in categories.keys():
                    row.append(people_working[pkey][cat_key])
                people_selected_rows += [row]
                # if check address then delete all those at this address (will NOT delete the one we want as well)
                if settings.check_same_address:
                    people_to_delete, new_output_lines = get_people_at_same_address(people_working, pkey,
                                                                                    settings.check_same_address_columns)
                    output_lines += new_output_lines
                    num_same_address_deleted += len(new_output_lines)  # don't include original
                    # then delete this/these people at the same address from the reserve/remaining pool
                    del people_working[pkey]
                    num_same_address_deleted += 1
                    for del_person_key in people_to_delete:
                        del people_working[del_person_key]
                else:
                    del people_working[pkey]

            # add the columns to keep into remaining people
            # as above all these values are all in people_working but this is tidier...
            for pkey, person in people_working.items():
                row = [pkey]
                for col in settings.columns_to_keep:
                    row.append(people_working[pkey][col])
                for cat_key in categories.keys():
                    row.append(people_working[pkey][cat_key])
                people_remaining_rows += [row]
            dupes = self._output_selected_remaining(settings, people_selected_rows, people_remaining_rows)
            if settings.check_same_address and self.gen_rem_tab == 'on':
                output_lines += [
                    "Deleted {} people from remaining file who had the same address as selected people.".format(
                        num_same_address_deleted)]
                m = min(30, len(dupes))
                output_lines += [
                    "In the remaining tab there are {} people who share the same address as someone else in the tab. We highlighted the first {} of these. The full list of lines is {}".format(
                        len(dupes), m, dupes)]
        return output_lines


class PeopleAndCatsCSV(PeopleAndCats):

    def __init__(self):
        super(PeopleAndCatsCSV, self).__init__()
        # self.people_csv_content = ''
        self.selected_file = StringIO()
        self.remaining_file = StringIO()

    def get_selected_file(self):
        return self.selected_file

    def get_remaining_file(self):
        return self.remaining_file

    def load_cats(self, file_contents, dummy_category_tab, settings: Settings):
        self.category_content_loaded = True
        category_file = StringIO(file_contents)
        category_reader = csv.DictReader(category_file)
        return self._read_in_cats(list(category_reader.fieldnames), category_reader)

    def load_people(self, settings: Settings, file_contents='', dummy_respondents_tab='', dummy_category_tab='',
                    dummy_gen_rem=''):
        if file_contents != '':
            self.people_content_loaded = True
        people_file = StringIO(file_contents)
        people_data = csv.DictReader(people_file)
        return self._init_categories_people(list(people_data.fieldnames), people_data, settings)

    # Actually useful to also write to a file all those who are NOT selected for later selection if people pull out etc
    # BUT, we should not include in this people from the same address as someone who has been selected!
    def _output_selected_remaining(self, settings: Settings, people_selected_rows, people_remaining_rows):
        # we have succeeded in CSV so can activate buttons in GUI...
        self.enable_file_download = True

        people_selected_writer = csv.writer(
            self.selected_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
        )
        for row in people_selected_rows:
            people_selected_writer.writerow(row)

        people_remaining_writer = csv.writer(
            self.remaining_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
        )
        for row in people_remaining_rows:
            people_remaining_writer.writerow(row)


class PeopleAndCatsGoogleSheet(PeopleAndCats):
    scope = None
    creds = None
    client = None
    #   category_tab_name = "Categories"
    #   respondents_tab_name = "Respondents"##Nick is taking this out
    original_selected_tab_name = "Original Selected - output - "
    selected_tab_name = "Selected"
    columns_selected_first = "C"
    column_selected_blank_num = 6
    remaining_tab_name = "Remaining - output - "
    new_tab_default_size_rows = "2"
    new_tab_default_size_cols = "40"

    def __init__(self):
        super(PeopleAndCatsGoogleSheet, self).__init__()
        self.g_sheet_name = ''
        self.respondents_tab_name = ''
        self.category_tab_name = ''
        self.spreadsheet = None

    def _tab_exists(self, tab_name):
        if self.spreadsheet == None:
            return False
        tab_list = self.spreadsheet.worksheets()
        for tab in tab_list:
            if tab.title == tab_name:
                return True
        return False

    def _clear_or_create_tab(self, tab_name, other_tab_name, inc):
        # this now does not clear data but increments the sheet number...
        num = 0
        tab_ready = None
        tab_name_new = tab_name + str(num)
        other_tab_name_new = other_tab_name + str(num)
        while tab_ready == None:
            if self._tab_exists(tab_name_new) or self._tab_exists(other_tab_name_new):
                num += 1
                tab_name_new = tab_name + str(num)
                other_tab_name_new = other_tab_name + str(num)
            # tab_ready = self.spreadsheet.worksheet(tab_name )
            # tab_ready.clear()
            else:
                if inc == -1:
                    tab_name_new = tab_name + str(num - 1)
                tab_ready = self.spreadsheet.add_worksheet(title=tab_name_new, rows=self.new_tab_default_size_rows,
                                                           cols=self.new_tab_default_size_cols)
        return tab_ready

    def load_cats(self, g_sheet_name, category_tab_name, settings: Settings):
        self.category_content_loaded = True
        self.g_sheet_name = g_sheet_name
        self.category_tab_name = category_tab_name

        json_file_name = settings.json_file_path
        min_val = 0
        max_val = 0
        msg = []
        try:
            if self.scope is None:
                self.scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                self.creds = ServiceAccountCredentials.from_json_keyfile_name(json_file_name, self.scope)
                self.client = gspread.authorize(self.creds)
            self.spreadsheet = self.client.open(self.g_sheet_name)
            msg += ["Opened Google Sheet: '{}'. ".format(self.g_sheet_name)]
            if self._tab_exists(self.category_tab_name):
                tab_cats = self.spreadsheet.worksheet(self.category_tab_name)
                cat_head_input = tab_cats.row_values(1)
                cat_input = tab_cats.get_all_records()
                new_msg, min_val, max_val = self._read_in_cats(cat_head_input, cat_input)
                msg += ["Read in '{}' tab in above Google sheet.".format(self.category_tab_name)]
                msg += new_msg
            else:
                msg += ["Error in Google sheet: no tab called '{}' found. ".format(self.category_tab_name)]
                self.category_content_loaded = False
        except gspread.SpreadsheetNotFound:
            msg += ["Google spreadsheet not found: {}. ".format(self.g_sheet_name)]
            self.category_content_loaded = False
        return msg, min_val, max_val

    ##Added respondents_tab_name, category_tab_name and gen_rem_tab as an argument
    def load_people(self, settings: Settings, dummy_file_contents, respondents_tab_name, category_tab_name,
                    gen_rem_tab):
        self.people_content_loaded = True
        self.respondents_tab_name = respondents_tab_name  ##Added for respondents tab text box.
        self.category_tab_name = category_tab_name  ##Added for category tab text box.
        self.gen_rem_tab = gen_rem_tab  ##Added for checkbox.
        msg = []
        # self.number_selections = int(number_selections) ##Added for multiple selections. Brett removed - now in base class
        try:
            if self._tab_exists(self.respondents_tab_name):
                tab_people = self.spreadsheet.worksheet(self.respondents_tab_name)
                # if we don't read this in here we can't check if there are 2 columns with the same name
                people_head_input = tab_people.row_values(1)
                # the numericise_ignore doesn't convert the phone numbers to ints...
                people_input = tab_people.get_all_records(numericise_ignore=['all'])
                msg = ["Reading in '{}' tab in above Google sheet.".format(self.respondents_tab_name)]
                msg += self._init_categories_people(people_head_input, people_input, settings)
            else:
                msg = ["Error in Google sheet: no tab called '{}' found. ".format(self.respondents_tab_name)]
                self.people_content_loaded = False
        except gspread.SpreadsheetNotFound:
            msg += ["Google spreadsheet not found: {}. ".format(self.g_sheet_name)]
            self.people_content_loaded = False
        return msg

    def _output_selected_remaining(self, settings: Settings, people_selected_rows, people_remaining_rows):

        # if self.number_selections > 1 then self.gen_rem_tab=='off'
        assert (self.number_selections == 1 or (self.number_selections > 1 and self.gen_rem_tab == 'off'))
        tab_original_selected = self._clear_or_create_tab(self.original_selected_tab_name, self.remaining_tab_name, 0)
        tab_original_selected.update(people_selected_rows)
        tab_original_selected.format("A1:U1",
                                     {"backgroundColor": {"red": 153 / 255, "green": 204 / 255, "blue": 255 / 255}})
        dupes2 = []
        if self.gen_rem_tab == 'on':
            tab_remaining = self._clear_or_create_tab(self.remaining_tab_name, self.original_selected_tab_name, -1)
            tab_remaining.update(people_remaining_rows)
            tab_remaining.format("A1:U1",
                                 {"backgroundColor": {"red": 153 / 255, "green": 204 / 255, "blue": 255 / 255}})
            # highlight any people in remaining tab at the same address
            if settings.check_same_address:
                csa1 = settings.check_same_address_columns[0]
                col1 = tab_remaining.find(csa1).col
                csa2 = settings.check_same_address_columns[1]
                col2 = tab_remaining.find(csa2).col
                dupes = []
                n = len(people_remaining_rows)
                for i in range(n):
                    rowrem1 = people_remaining_rows[i]
                    for j in range(i + 1, n):
                        rowrem2 = people_remaining_rows[j]
                        if rowrem1 != rowrem2 and rowrem1[col1 - 1] == rowrem2[col1 - 1] and rowrem1[col2 - 1] == \
                                rowrem2[col2 - 1]:
                            # cell = i#tab_remaining.find(rowrem1[0])
                            dupes.append(i + 1)
                            dupes.append(j + 1)
                dupes4 = []
                [dupes4.append(x) for x in dupes if x not in dupes4]
                dupes2 = sorted(dupes4)
                dupes3 = []
                m = min(30, len(dupes2))
                for i in range(m):
                    dupes3.append(dupes2[i])
                for row in dupes3:
                    tab_remaining.format(str(row), {"backgroundColor": {"red": 5, "green": 2.5, "blue": 0}})
        return dupes2


###################################
#
# End PeopleAndCats classes...
#
#  ... of course in theory almost all of the below functions could be integrated into
#   the above (base) class but may be useful to keep separated? Or at least I can't be bothered
#   integrating them in now ...
#
###################################


# create READABLE example file of people
def create_readable_sample_file(categories, people_file: typing.TextIO, number_people_example_file, settings: Settings):
    example_people_writer = csv.writer(
        people_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
    )
    cat_keys = categories.keys()
    example_people_writer.writerow([settings.id_column] + settings.columns_to_keep + list(cat_keys))
    for x in range(number_people_example_file):
        row = ["p{}".format(x)]
        for col in settings.columns_to_keep:
            row.append(col + str(x))
        for cat_key, cats in categories.items():  # e.g. gender
            cat_items_list_weighted = []
            for cats_key, cats_item in cats.items():  # e.g. male
                for y in range(cats_item["max"]):
                    cat_items_list_weighted.append(cats_key)
            # random_cat_value = random.choice(list(cats.keys()))
            random_cat_value = random.choice(cat_items_list_weighted)
            row.append(random_cat_value)
        example_people_writer.writerow(row)


# when a category is full we want to delete everyone in it
def delete_all_in_cat(categories, people, cat_check_key, cat_check_value):
    people_to_delete = []
    for pkey, person in people.items():
        if person[cat_check_key] == cat_check_value:
            people_to_delete.append(pkey)
            #for pcat, pval in person.items():
            for cat_key in categories.keys():
                #cat_item = categories[pcat][pval]
                cat_item = categories[cat_key][person[cat_key]]
                cat_item["remaining"] -= 1
                if cat_item["remaining"] == 0 and cat_item["selected"] < cat_item["min"]:
                    raise SelectionError(
                        "SELECTION IMPOSSIBLE: FAIL in delete_all_in_cat as after previous deletion no one/not enough left in " + cat_key
                    )
    for p in people_to_delete:
        del people[p]
    # return the number of people deleted and the number of people left
    return len(people_to_delete), len(people)


# selected = True means we are deleting because they have been chosen,
# otherwise they are being deleted because they live at same address as someone selected
def really_delete_person(categories, people, pkey, selected):
    for pcat, pval in people[pkey].items():
        cat_item = categories[pcat][pval]
        if selected:
            cat_item["selected"] += 1
        cat_item["remaining"] -= 1
        if cat_item["remaining"] == 0 and cat_item["selected"] < cat_item["min"]:
            raise SelectionError("FAIL in delete_person: no one left in " + pval)
    del people[pkey]


def get_people_at_same_address(people, pkey, check_same_address_columns):
    primary_address1 = people[pkey][check_same_address_columns[0]]
    primary_zip = people[pkey][check_same_address_columns[1]]
    # there may be multiple people to delete, and deleting them as we go gives an error
    people_to_delete = []
    output_lines = []
    for compare_key in people.keys():
        # don't get yourself!?
        if (
                pkey != compare_key
                and primary_address1 == people[compare_key][check_same_address_columns[0]]
                and primary_zip == people[compare_key][check_same_address_columns[1]]
        ):
            # found same address
            if people_to_delete != []:
                output_lines += [
                    "Found someone with the same address as a selected person,"
                    " so deleting him/her. Address: {} , {}".format(primary_address1, primary_zip)
                ]
            people_to_delete.append(compare_key)
    return people_to_delete, output_lines


# lucky person has been selected - delete person from DB
def delete_person(categories, people, pkey, check_same_address, check_same_address_columns):
    output_lines = []
    # recalculate all category values that this person was in
    person = people[pkey]
    # check if there are other people at the same address - if so, remove them!
    if check_same_address:
        people_to_delete, output_lines = get_people_at_same_address(people, pkey, check_same_address_columns)
        # then delete this/these people at the same address
        for del_person_key in people_to_delete:
            really_delete_person(categories, people, del_person_key, False)
    # delete the actual person after checking for people at the same address
    really_delete_person(categories, people, pkey, True)
    # then check if any cats of selected person is (was) in are full
    for (pcat, pval) in person.items():
        cat_item = categories[pcat][pval]
        if cat_item["selected"] == cat_item["max"]:
            output_lines += ["Category {} full - deleting people...".format(pval)]
            num_deleted, num_left = delete_all_in_cat(categories, people, pcat, pval)
            output_lines[-1] += " Deleted {}, {} left.".format(num_deleted, num_left)
    return output_lines


# returns dict of category key, category item name, random person number
def find_max_ratio_cat(categories):
    ratio = -100.0
    key_max = ""
    index_max_name = ""
    random_person_num = -1
    for cat_key, cats in categories.items():
        for cat, cat_item in cats.items():
            # if there are zero remaining, or if there are less than how many we need we're in trouble
            if cat_item["selected"] < cat_item["min"] and cat_item["remaining"] < (
                    cat_item["min"] - cat_item["selected"]
            ):
                raise SelectionError(
                    "FAIL in find_max_ratio_cat: No people (or not enough) in category " + cat
                )
            # if there are none remaining, it must be because we have reached max and deleted them
            # or, if max = 0, then we don't want any of these (could happen when seeking replacements)
            if cat_item["remaining"] != 0 and cat_item["max"] != 0:
                item_ratio = (cat_item["min"] - cat_item["selected"]) / float(cat_item["remaining"])
                # print item['name'],': ', item['remaining'], 'ratio : ', item_ratio
                if item_ratio > 1:  # trouble!
                    raise SelectionError("FAIL in find_max_ratio_cat: a ratio > 1...")
                if item_ratio > ratio:
                    ratio = item_ratio
                    key_max = cat_key
                    index_max_name = cat
                    random_person_num = random.randint(1, cat_item["remaining"])
    if debug > 0:
        print("Max ratio: {} for {} {}".format(ratio, key_max, index_max_name))
        # could also append random_person_num
    return {
        "ratio_cat": key_max,
        "ratio_cat_val": index_max_name,
        "ratio_random": random_person_num,
    }


# First return is True if selection has been successful, second return are messages
# Print category info - if people_selected is empty it is assumed the output should be how many people initially
def print_category_info(categories, people, people_selected, number_people_wanted):
    if len(people_selected) > 1:
        return ["<p>We do not calculate target details for multiple selections - please see your output files.</p>"]
    initial_print = True if len(people_selected) == 0 else False
    # count and print
    report_msg = "<table border='1' cellpadding='5'>"
    if initial_print:
        report_msg += "<tr><th colspan='2'>Category</th><th>Initially</th><th>Want</th></tr>"
    else:
        report_msg += "<tr><th colspan='2'>Category</th><th>Selected</th><th>Want</th></tr>"
    # create a local version of this to count stuff in, as this might be called from places that don't track this info
    # and reset the info just in case it has been used
    categories_working = copy.deepcopy(categories)
    for cat_key, cats in categories_working.items():
        for cat, cat_item in cats.items():
            cat_item["selected"] = 0
    # count those either initially or selected, but use the same data item...
    if initial_print:
        for pkey, person in people.items():
            for feature in categories.keys():
                value = person[feature]
                categories_working[feature][value]["selected"] += 1
    else:
        assert(len(people_selected) == 1)
        for person in people_selected[0]:
            for feature in categories.keys():
                value = people[person][feature]
                categories_working[feature][value]["selected"] += 1

    # print out how many in each
    for cat_key, cats in categories_working.items():
        for cat, cat_item in cats.items():
            if initial_print: # don't bother about percents...
                report_msg += "<tr><td>{}</td><td>{}</td><td>{}</td><td>[{},{}]</td></tr>".format(
                    cat_key,
                    cat,
                    cat_item["selected"],
                    cat_item["min"],
                    cat_item["max"],
                )
            else:
                percent_selected = round(
                    cat_item["selected"] * 100 / float(number_people_wanted), 2
                )
                report_msg += "<tr><td>{}</td><td>{}</td><td>{} ({}%)</td><td>[{},{}]</td></tr>".format(
                    cat_key,
                    cat,
                    cat_item["selected"],
                    percent_selected,
                    cat_item["min"],
                    cat_item["max"],
                )
    report_msg += "</table>"
    return [report_msg]


def check_category_selected(categories, people, people_selected, number_selections):
    hit_targets = True
    last_cat_fail = ''
    if number_selections > 1:
        return hit_targets, ["<p>No target checks done for multiple selections - please see your output files.</p>"]
    #else:
    # count and print
    # create a local version of this to count stuff in, as this might be called from places that don't track this info
    # and reset the info just in case it has been used
    categories_working = copy.deepcopy(categories)
    for cat_key, cats in categories_working.items():
        for cat, cat_item in cats.items():
            cat_item["selected"] = 0
    # count those selected - but not at the start when people_selected is empty (the initial values should be zero)
    if len(people_selected) == 1:
        for person in people_selected[0]:
            for feature in categories.keys():
                value = people[person][feature]
                categories_working[feature][value]["selected"] += 1
    # check if quotas have been met or not
    for cat_key, cats in categories_working.items():
        for cat, cat_item in cats.items():
            if cat_item["selected"] < cat_item["min"] or cat_item["selected"] > cat_item["max"]:
                hit_targets = False
                last_cat_fail = cat
    report_msg = "<p>Failed to get minimum or got more than maximum in (at least) category: {}</p>".format(
        last_cat_fail)
    report_msg = '' if hit_targets == True else "<p>Failed to get minimum or got more than maximum in (at least) category: {}</p>".format(last_cat_fail)
    return hit_targets, [report_msg]


def _distribution_stats(people: Dict[str, Dict[str, str]], committees: List[FrozenSet[str]],
                        probabilities: List[float]) -> List[str]:
    output_lines = []

    assert len(committees) == len(probabilities)
    num_non_zero = sum([1 for prob in probabilities if prob > 0])
    output_lines.append(f"Algorithm produced distribution over {len(committees)} committees, out of which "
                        f"{num_non_zero} are chosen with positive probability.")

    individual_probabilities = {id: 0 for id in people}
    containing_committees = {id: [] for id in people}
    for committee, prob in zip(committees, probabilities):
        if prob > 0:
            for id in committee:
                individual_probabilities[id] += prob
                containing_committees[id].append(committee)

    table = ["<table border='1' cellpadding='5'><tr><th>Agent ID</th><th>Probability of selection</th><th>Included in #"
             "of committees</th></tr>"]

    for _, id in sorted((prob, id) for id, prob in individual_probabilities.items()):
        table.append(f"<tr><td>{id}</td><td>{individual_probabilities[id]:.4%}</td><td>{len(containing_committees[id])}"
                     "</td></tr>")
    table.append("</table>")
    output_lines.append("".join(table))

    return output_lines


def _output_panel_table(panels: List[FrozenSet[str]], probs: List[float]):
    def panel_to_tuple(panel: FrozenSet[str]) -> Tuple[str]:
        return tuple(sorted(panel))

    k = len(panels[0])
    dist = {}
    for panel, prob in zip(panels, probs):
        assert len(panel) == k
        tup = panel_to_tuple(panel)
        if tup not in dist:
            dist[tup] = 0.
        dist[tup] += prob

    with codecs.open("table.csv", "w", "utf8") as file:
        file.write(",".join(["Panel number", "Suggested probability"] + [f"agent {i}" for i in range(1, k + 1)]))
        file.write("\n")
        number = 0
        for tup, prob in dist.items():
            if prob > 0:
                file.write(f"{number},{prob},")
                number += 1
                file.write(",".join(f'"{id}"' for id in tup))
                file.write("\n")


def pipage_rounding(marginals: List[Tuple[Any, float]]) -> List[Any]:
    assert all(0. <= p <= 1. for _, p in marginals)

    outcomes = []
    while True:
        if len(marginals) == 0:
            return outcomes
        elif len(marginals) == 1:
            obj, prob = marginals[0]
            if random.random() < prob:
                outcomes.append(obj)
            marginals = []
        else:
            obj0, prob0 = marginals[0]
            if prob0 > 1. - EPS2:
                outcomes.append(obj0)
                marginals = marginals[1:]
                continue
            elif prob0 < EPS2:
                marginals = marginals[1:]
                continue

            obj1, prob1 = marginals[1]
            if prob1 > 1. - EPS2:
                outcomes.append(obj1)
                marginals = [marginals[0]] + marginals[2:]
                continue
            elif prob1 < EPS2:
                marginals = [marginals[0]] + marginals[2:]
                continue

            inc0_dec1_amount = min(1. - prob0, prob1)  # maximal amount that prob0 can be increased and prob1 can be
                                                       # decreased before they drop below 0 or above 1
            dec0_inc1_amount = min(prob0, 1. - prob1)
            choice_probability = dec0_inc1_amount / (inc0_dec1_amount + dec0_inc1_amount)

            if random.random() < choice_probability:  # increase prob0 and decrease prob1
                prob0 += inc0_dec1_amount
                prob1 -= inc0_dec1_amount
            else:
                prob0 -= dec0_inc1_amount
                prob1 += dec0_inc1_amount
            marginals = [(obj0, prob0), (obj1, prob1)] + marginals[2:]


def standardize_distribution(committees: List[FrozenSet[str]], probabilities: List[float]) \
        -> Tuple[List[FrozenSet[str]], List[float]]:
    assert len(committees) == len(probabilities)
    new_committees = []
    new_probabilities = []
    for committee, prob in zip(committees, probabilities):
        if prob >= EPS2:
            new_committees.append(committee)
            new_probabilities.append(prob)
    prob_sum = sum(new_probabilities)
    new_probabilities = [prob / prob_sum for prob in new_probabilities]
    return new_committees, new_probabilities


def lottery_rounding(committees: List[FrozenSet[str]], probabilities: List[float], number_selections: int) \
        -> List[FrozenSet[str]]:
    assert len(committees) == len(probabilities)
    assert number_selections >= 1

    num_copies = []
    residuals = []
    for committee, prob in zip(committees, probabilities):
        scaled_prob = prob * number_selections
        num_copies.append(int(scaled_prob))  # give lower quotas
        residuals.append(scaled_prob - int(scaled_prob))
    assert abs(sum(residuals) - round(sum(residuals))) <= .0001

    rounded_up_indices = pipage_rounding(list(enumerate(residuals)))
    assert round(sum(residuals)) == len(rounded_up_indices)
    for committee_index in rounded_up_indices:
        num_copies[committee_index] += 1

    committee_lottery = []
    for committee, committee_copies in zip(committees, num_copies):
        for _ in range(committee_copies):
            committee_lottery.append(committee)

    return committee_lottery


def find_random_sample(categories: Dict[str, Dict[str, Dict[str, int]]], people: Dict[str, Dict[str, str]],
                       columns_data: Dict[str, Dict[str, str]], number_people_wanted: int, check_same_address: bool,
                       check_same_address_columns: List[str], selection_algorithm: str, test_selection: bool,
                       number_selections: int) \
        -> Tuple[List[FrozenSet[str]], List[str]]:
    """Main algorithm to try to find one or multiple random committees.

    Args:
        categories: categories["feature"]["value"] is a dictionary with keys "min", "max", "min_flex", "max_flex",
            "selected", "remaining".
        people: people["nationbuilder_id"] is dictionary mapping "feature" to "value" for a person.
        columns_data: columns_data["nationbuilder_id"] is dictionary mapping "contact_field" to "value" for a person.
        number_people_wanted:
        check_same_address:
        check_same_address_columns: list of contact fields of columns that have to be equal for being
            counted as residing at the same address
        selection_algorithm: one out of "legacy", "maximin", "leximin", or "nash"
        test_selection: if set, do not do a random selection, but just return some valid panel. Useful for quickly
            testing whether quotas are satisfiable, but should always be false for the actual selection!
        number_selections: how many panels to return. Most of the time, this should be set to `1`, which means that
            a single panel is chosen. When specifying a value n ≥ 2, the function will return a list of length n,
            containing multiple panels (some panels might be repeated in the list). In this case the eventual panel
            should be drawn uniformly at random from the returned list.
    Returns:
        (committee_lottery, output_lines)
        `committee_lottery` is a list of committees, where each committee is a frozen set of pool member ids guaranteed
            to satisfy the constraints on a feasible committee.
        `output_lines` is a list of debug strings.
    Raises:
        InfeasibleQuotasError if the quotas cannot be satisfied, which includes a suggestion for how to modify them.
        SelectionError in multiple other failure cases.
    Side Effects:
        Existing callers assume the "selected" and "remaining" fields in `categories` to be changed.
    """
    if not all("min_flex" in categories[feature][value] and "max_flex" in categories[feature][value]
               for feature in categories for value in categories[feature]):
        raise ValueError("By the time they're fed into `find_random_sample`, the `categories` argument should always "
                         "contain the new fields 'min_flex' and 'max_flex'. If they're not in the categories file, the "
                         "code should set default values before calling this function.")
    for feature in categories:
        for value in categories[feature]:
            info = categories[feature][value]
            if not (info["min_flex"] <= info["min"] <= info["max"] <= info["max_flex"]):
                raise ValueError(f"For feature ({feature}: {value}), the different quotas have incompatible values. "
                                 f"It must hold that min_flex ({info['min_flex']}) <= min ({info['min']}) <= max "
                                 f"({info['max']}) <= max_flex ({info['max_flex']}).")

    if check_same_address and len(check_same_address_columns) == 0:
        raise ValueError("Since the algorithm is configured to prevent multiple house members to appear on the same "
                         "panel (check_same_address = true), check_same_address_columns must not be empty.")

    # just go quick and nasty so we can hook up our charts ands tables :-)
    if test_selection:
        print("Running test selection.")
        if number_selections != 1:
            raise ValueError("Running the test selection does not support generating a transparent lottery, so, if "
                             "`test_selection` is true, `number_selections` must be 1.")
        return _find_any_committee(categories, people, columns_data, number_people_wanted, check_same_address,
                                   check_same_address_columns)

    output_lines = []
    if selection_algorithm == "leximin":
        try:
            import gurobipy
        except ModuleNotFoundError:
            output_lines.append(_print("The leximin algorithm requires the optimization library Gurobi to be installed "
                                       "(commercial, free academic licenses available). Switching to the simpler "
                                       "maximin algorithm, which can be run using open source solvers."))
            selection_algorithm = "maximin"

    if selection_algorithm == "legacy":
        if number_selections != 1:
            raise ValueError("Currently, the legacy algorithm does not support generating a transparent lottery, "
                             "so `number_selections` must be set to 1.")
        return find_random_sample_legacy(categories, people, columns_data, number_people_wanted, check_same_address,
                                         check_same_address_columns)
    elif selection_algorithm == "leximin":
        committees, probabilities, new_output_lines = find_distribution_leximin(categories, people, columns_data,
                                                                                number_people_wanted,
                                                                                check_same_address,
                                                                                check_same_address_columns)
    elif selection_algorithm == "maximin":
        committees, probabilities, new_output_lines = find_distribution_maximin(categories, people, columns_data,
                                                                                number_people_wanted,
                                                                                check_same_address,
                                                                                check_same_address_columns)
    elif selection_algorithm == "nash":
        committees, probabilities, new_output_lines = find_distribution_nash(categories, people, columns_data,
                                                                             number_people_wanted, check_same_address,
                                                                             check_same_address_columns)
    else:
        raise ValueError(f"Unknown selection algorithm {repr(selection_algorithm)}, must be either 'legacy', 'leximin',"
                         f" 'maximin', or 'nash'.")

    committees, probabilities = standardize_distribution(committees, probabilities)
    if len(committees) > len(people):
        print("INFO: The distribution over panels what is known as a 'basic solution'. There is no reason for concern "
              "about the correctness of your output, but we'd appreciate if you could reach out to panelot"
              f"@paulgoelz.de with the following information: algorithm={selection_algorithm}, "
              f"num_panels={len(committees)}, num_agents={len(people)}, min_probs={min(probabilities)}.")

    assert len(set(committees)) == len(committees)

    output_lines += new_output_lines
    output_lines += _distribution_stats(people, committees, probabilities)

    committee_lottery = lottery_rounding(committees, probabilities, number_selections)

    return committee_lottery, output_lines


def find_random_sample_legacy(categories: Dict[str, Dict[str, Dict[str, int]]], people: Dict[str, Dict[str, str]],
                              columns_data: Dict[str, Dict[str, str]], number_people_wanted: int,
                              check_same_address: bool, check_same_address_columns: List[str]) \
        -> Tuple[List[FrozenSet[str]], List[str]]:
    output_lines = ["Using legacy algorithm."]
    people_selected = set()
    for count in range(number_people_wanted):
        ratio = find_max_ratio_cat(categories)
        # find randomly selected person with the category value
        for pkey, pvalue in people.items():
            if pvalue[ratio["ratio_cat"]] == ratio["ratio_cat_val"]:
                # found someone with this category value...
                ratio["ratio_random"] -= 1
                if ratio["ratio_random"] == 0:  # means they are the random one we want
                    if debug > 0:
                        print("Found random person in this cat... adding them")
                    assert pkey not in people_selected
                    people_selected.add(pkey)
                    output_lines += delete_person(categories, people, pkey, check_same_address,
                                                  check_same_address_columns)
                    break
        if count < (number_people_wanted - 1) and len(people) == 0:
            raise SelectionError("Fail! We've run out of people...")
    return [frozenset(people_selected)], output_lines


def _ilp_results_to_committee(variables: Dict[str, mip.entities.Var]) -> FrozenSet[str]:
    try:
        res = frozenset(id for id in variables if variables[id].x > 0.5)
    except Exception as e:  # unfortunately, MIP sometimes throws generic Exceptions rather than a subclass.
        raise ValueError(f"It seems like some variables does not have a value. Original exception: {e}.")

    return res


def _same_address(columns_data1: Dict[str, str], columns_data2: Dict[str, str], check_same_address_columns: List[str]) \
        -> bool:
    return all(columns_data1[column] == columns_data2[column] for column in check_same_address_columns)


def _print(message: str) -> str:
    print(message)
    return message


def _compute_households(people: Dict[str, Dict[str, str]], columns_data: Dict[str, Dict[str, str]],
                        check_same_address_columns: List[str]) -> Dict[str, int]:
    ids = list(people.keys())
    households = {id: None for id in people}  # for each agent, the id of the earliest person with same address

    counter = 0
    for i, id1 in enumerate(ids):
        if households[id1] is not None:
            continue
        households[id1] = counter
        for id2 in ids[i + 1:]:
            if households[id2] is None and _same_address(columns_data[id1], columns_data[id2],
                                                         check_same_address_columns):
                households[id2] = counter
        counter += 1

    if counter == 1:
        print("Warning: All pool members live in the same household. Probably, the configuration is wrong?")

    return households


class InfeasibleQuotasError(Exception):
    def __init__(self, quotas: Dict[Tuple[str, str], Tuple[int, int]], output: List[str]):
        self.quotas = quotas
        self.output = ["The quotas are infeasible:"] + output

    def __str__(self):
        return "\n".join(self.output)


class InfeasibleQuotasCantRelaxError(Exception):
    def __init__(self, message: str):
        self.message = message


def _relax_infeasible_quotas(categories: Dict[str, Dict[str, Dict[str, int]]], people: Dict[str, Dict[str, str]],
                             number_people_wanted: int, check_same_address: bool,
                             households: Optional[Dict[str, int]] = None,
                             ensure_inclusion: typing.Collection[Iterable[str]] = ((),)) \
        -> Tuple[Dict[Tuple[str, str], Tuple[int, int]], List[str]]:
    """Assuming that the quotas are not satisfiable, suggest a minimal relaxation that would be.

    Args:
        categories: quotas in the format described in `find_random_sample`
        people: pool members in the format described in `find_random_sample`
        number_people_wanted: desired size of the panel
        check_same_address: whether members from the same household cannot simultaneously appear
        households: if `check_same_address` is given, a dictionary mapping pool member ids to integers representing
            households. if two agents have the same value in the dictionary, they are considered to live together.
        ensure_inclusion: allows to specify that some panels should contain specific sets of agents. for example,
            passing `(("a",), ("b", "c"))` means that the quotas should be relaxed such that some valid panel contains
            agent "a" and some valid panel contains both agents "b" and "c". the default of `((),)` just requires
            a panel to exist, without further restrictions.
    """
    model = mip.Model(sense=mip.MINIMIZE)
    model.verbose = debug

    assert len(ensure_inclusion) > 0  # otherwise, the existence of a panel is not required

    # for every feature, a variable for how much the upper and lower quotas are relaxed
    feature_values = [(feature, value) for feature in categories for value in categories[feature]]
    min_vars = {fv: model.add_var(var_type=mip.INTEGER, lb=0.) for fv in feature_values}
    max_vars = {fv: model.add_var(var_type=mip.INTEGER, lb=0.) for fv in feature_values}

    # relaxations cannot drop lower quotas below min_flex or upper quotas beyond max_flex
    for feature, value in feature_values:
        model.add_constr(
            categories[feature][value]["min"] - min_vars[(feature, value)] >= categories[feature][value]["min_flex"])
        model.add_constr(
            categories[feature][value]["max"] + max_vars[(feature, value)] <= categories[feature][value]["max_flex"])

    # we might not be able to select multiple persons from the same household
    people_by_household = {}
    if check_same_address:
        assert households is not None

        for id, household in households.items():
            if household not in people_by_household:
                people_by_household[household] = []
            people_by_household[household].append(id)

    for inclusion_set in ensure_inclusion:
        # for every person, we have a binary variable indicating whether they are in the committee
        agent_vars = {id: model.add_var(var_type=mip.BINARY) for id in people}
        for agent in inclusion_set:
            model.add_constr(agent_vars[agent] == 1)

        # we have to select exactly `number_people_wanted` many persons
        model.add_constr(mip.xsum(agent_vars.values()) == number_people_wanted)

        # we have to respect the relaxed quotas
        for feature, value in feature_values:
            number_feature_value_agents = mip.xsum(agent_vars[id] for id, person in people.items()
                                                   if person[feature] == value)
            model.add_constr(
                number_feature_value_agents >= categories[feature][value]["min"] - min_vars[(feature, value)])
            model.add_constr(
                number_feature_value_agents <= categories[feature][value]["max"] + max_vars[(feature, value)])

            if check_same_address:
                for household, members in people_by_household.items():
                    if len(members) >= 2:
                        model.add_constr(mip.xsum(agent_vars[id] for id in members) <= 1)

    def reduction_weight(feature, value):
        """Make the algorithm more recluctant to reduce lower quotas that are already low. If the lower quotas was 1,
        reducing it one more (to 0) is 3 times more salient than increasing a quota by 1. This bonus tampers off
        quickly, reducing from 10 is only 1.2 times as salient as an increase."""
        old_quota = categories[feature][value]["min"]
        if old_quota == 0:
            return 0  # cannot be relaxed anyway
        else:
            return 1 + 2 / old_quota

    # we want to minimize the amount by which we have to relax quotas
    model.objective = mip.xsum(
        [reduction_weight(*fv) * min_vars[fv] for fv in feature_values] + [max_vars[fv] for fv in feature_values])

    # Optimize once without any constraints to check if no feasible committees exist at all.
    status = model.optimize()
    if status == mip.OptimizationStatus.INFEASIBLE:
        raise InfeasibleQuotasCantRelaxError("No feasible committees found, even with relaxing the quotas. Most "
                                             "likely, quotas would have to be relaxed beyond what the 'min_flex' and "
                                             "'max_flex' columns allow.")
    elif status != mip.OptimizationStatus.OPTIMAL:
        raise SelectionError(f"No feasible committees found, solver returns code {status} (see "
                             f"https://docs.python-mip.com/en/latest/classes.html#optimizationstatus). Either the pool "
                             f"is very bad or something is wrong with the solver.")

    output_lines = []
    new_quotas = {}
    for fv in feature_values:
        feature, value = fv
        lower = categories[feature][value]["min"] - round(min_vars[fv].x)
        assert lower <= categories[feature][value]["min"]
        if lower < categories[feature][value]["min"]:
            output_lines.append(f"Recommend lowering lower quota of {feature}:{value} to {lower}.")
        upper = categories[feature][value]["max"] + round(max_vars[fv].x)
        assert upper >= categories[feature][value]["max"]
        if upper > categories[feature][value]["max"]:
            assert lower == categories[feature][value]["min"]
            output_lines.append(f"Recommend raising upper quota of {feature}:{value} to {upper}.")
        new_quotas[fv] = (lower, upper)

    return new_quotas, output_lines


def _setup_committee_generation(categories: Dict[str, Dict[str, Dict[str, int]]], people: Dict[str, Dict[str, str]],
                                number_people_wanted: int, check_same_address: bool,
                                households: Optional[Dict[str, int]]) \
        -> Tuple[mip.model.Model, Dict[str, mip.entities.Var]]:
    model = mip.Model(sense=mip.MAXIMIZE)
    model.verbose = debug

    # for every person, we have a binary variable indicating whether they are in the committee
    agent_vars = {id: model.add_var(var_type=mip.BINARY) for id in people}

    # we have to select exactly `number_people_wanted` many persons
    model.add_constr(mip.xsum(agent_vars.values()) == number_people_wanted)

    # we have to respect quotas
    for feature in categories:
        for value in categories[feature]:
            number_feature_value_agents = mip.xsum(agent_vars[id] for id, person in people.items()
                                                   if person[feature] == value)
            model.add_constr(number_feature_value_agents >= categories[feature][value]["min"])
            model.add_constr(number_feature_value_agents <= categories[feature][value]["max"])

    # we might not be able to select multiple persons from the same household
    if check_same_address:
        people_by_household = {}
        for id, household in households.items():
            if household not in people_by_household:
                people_by_household[household] = []
            people_by_household[household].append(id)

        for household, members in people_by_household.items():
            if len(members) >= 2:
                model.add_constr(mip.xsum(agent_vars[id] for id in members) <= 1)

    # Optimize once without any constraints to check if no feasible committees exist at all.
    status = model.optimize()
    if status == mip.OptimizationStatus.INFEASIBLE:
        new_quotas, output_lines = _relax_infeasible_quotas(categories, people, number_people_wanted,
                                                            check_same_address, households)
        raise InfeasibleQuotasError(new_quotas, output_lines)
    elif status != mip.OptimizationStatus.OPTIMAL:
        raise SelectionError(f"No feasible committees found, solver returns code {status} (see "
                             "https://docs.python-mip.com/en/latest/classes.html#optimizationstatus).")

    return model, agent_vars


def _find_any_committee(categories: Dict[str, Dict[str, Dict[str, int]]], people: Dict[str, Dict[str, str]],
                        columns_data: Dict[str, Dict[str, str]], number_people_wanted: int, check_same_address: bool,
                        check_same_address_columns: List[str]) -> Tuple[List[FrozenSet[str]], List[str]]:
    if check_same_address:
        households = _compute_households(people, columns_data, check_same_address_columns)
    else:
        households = None

    model, agent_vars = _setup_committee_generation(categories, people, number_people_wanted, check_same_address,
                                                    households)
    committee = _ilp_results_to_committee(agent_vars)
    return [committee], []


def _generate_initial_committees(new_committee_model: mip.model.Model, agent_vars: Dict[str, mip.entities.Var],
                                 multiplicative_weights_rounds: int) \
        -> Tuple[Set[FrozenSet[str]], FrozenSet[str], List[str]]:
    """To speed up the main iteration of the maximin and Nash algorithms, start from a diverse set of feasible
    committees. In particular, each agent that can be included in any committee will be included in at least one of
    these committees.
    """
    new_output_lines = []
    committees: Set[FrozenSet[str]] = set()  # Committees discovered so far
    covered_agents: Set[str] = set()  # All agents included in some committee

    # We begin using a multiplicative-weight stage. Each agent has a weight starting at 1.
    weights = {id: 1 for id in agent_vars}
    for i in range(multiplicative_weights_rounds):
        # In each round, we find a
        # feasible committee such that the sum of weights of its members is maximal.
        new_committee_model.objective = mip.xsum(weights[id] * agent_vars[id] for id in agent_vars)
        new_committee_model.optimize()
        new_set = _ilp_results_to_committee(agent_vars)

        # We then decrease the weight of each agent in the new committee by a constant factor. As a result, future
        # rounds will strongly prioritize including agents that appear in few committees.
        for id in new_set:
            weights[id] *= 0.8
        # We rescale the weights, which does not change the conceptual algorithm but prevents floating point problems.
        coefficient_sum = sum(weights.values())
        for id in agent_vars:
            weights[id] *= len(agent_vars) / coefficient_sum

        if new_set not in committees:
            # We found a new committee, and repeat.
            committees.add(new_set)
            for id in new_set:
                covered_agents.add(id)
        else:
            # If our committee is already known, make all weights a bit more equal again to mix things up a little.
            for id in agent_vars:
                weights[id] = 0.9 * weights[id] + 0.1

        print(
            f"Multiplicative weights phase, round {i + 1}/{multiplicative_weights_rounds}. Discovered {len(committees)}"
            " committees so far.")

    # If there are any agents that have not been included so far, try to find a committee including this specific agent.
    for id in agent_vars:
        if id not in covered_agents:
            new_committee_model.objective = agent_vars[id]  # only care about agent `id` being included.
            new_committee_model.optimize()
            new_set: FrozenSet[str] = _ilp_results_to_committee(agent_vars)
            if id in new_set:
                committees.add(new_set)
                for id2 in new_set:
                    covered_agents.add(id2)
            else:
                new_output_lines.append(_print(f"Agent {id} not contained in any feasible committee."))

    # We assume in this stage that the quotas are feasible.
    assert len(committees) >= 1

    if len(covered_agents) == len(agent_vars):
        new_output_lines.append(_print("All agents are contained in some feasible committee."))

    return committees, frozenset(covered_agents), new_output_lines


def _dual_leximin_stage(people: Dict[str, Dict[str, str]], committees: Set[FrozenSet[str]],
                        fixed_probabilities: Dict[str, float]):
    """This implements the dual LP described in `find_distribution_leximin`, but where P only ranges over the panels
    in `committees` rather than over all feasible panels:
    minimize ŷ - Σ_{i in fixed_probabilities} fixed_probabilities[i] * yᵢ
    s.t.     Σ_{i ∈ P} yᵢ ≤ ŷ                              ∀ P
             Σ_{i not in fixed_probabilities} yᵢ = 1
             ŷ, yᵢ ≥ 0                                     ∀ i

    Returns a Tuple[grb.Model, Dict[str, grb.Var], grb.Var]   (not in type signature to prevent global gurobi import.)
    """
    import gurobipy as grb
    assert len(committees) != 0

    model = grb.Model()
    agent_vars = {person: model.addVar(vtype=grb.GRB.CONTINUOUS, lb=0.) for person in people}  # yᵢ
    cap_var = model.addVar(vtype=grb.GRB.CONTINUOUS, lb=0.)  # ŷ
    model.addConstr(grb.quicksum(agent_vars[person] for person in people if person not in fixed_probabilities) == 1)
    for committee in committees:
        model.addConstr(grb.quicksum(agent_vars[person] for person in committee) <= cap_var)
    model.setObjective(cap_var - grb.quicksum(
        fixed_probabilities[person] * agent_vars[person] for person in fixed_probabilities),
                       grb.GRB.MINIMIZE)

    # Change Gurobi configuration to encourage strictly complementary (“inner”) solutions. These solutions will
    # typically allow to fix more probabilities per outer loop of the leximin algorithm.
    model.setParam("Method", 2)  # optimize via barrier only
    model.setParam("Crossover", 0)  # deactivate cross-over

    return model, agent_vars, cap_var


def find_distribution_leximin(categories: Dict[str, Dict[str, Dict[str, int]]], people: Dict[str, Dict[str, str]],
                              columns_data: Dict[str, Dict[str, str]], number_people_wanted: int,
                              check_same_address: bool, check_same_address_columns: List[str]) \
        -> Tuple[List[FrozenSet[str]], List[float], List[str]]:
    """Find a distribution over feasible committees that maximizes the minimum probability of an agent being selected
    (just like maximin), but breaks ties to maximize the second-lowest probability, breaks further ties to maximize the
    third-lowest probability and so forth.

    Arguments follow the pattern of `find_random_sample`.

    Returns:
        (committees, probabilities, output_lines)
        `committees` is a list of feasible committees, where each committee is represented by a frozen set of included
            agent ids.
        `probabilities` is a list of probabilities of equal length, describing the probability with which each committee
            should be selected.
        `output_lines` is a list of debug strings.
    """
    import gurobipy as grb

    output_lines = ["Using leximin algorithm."]
    grb.setParam("OutputFlag", 0)

    if check_same_address:
        households = _compute_households(people, columns_data, check_same_address_columns)
    else:
        households = None

    # Set up an ILP `new_committee_model` that can be used for discovering new feasible committees maximizing some
    # sum of weights over the agents.
    new_committee_model, agent_vars = _setup_committee_generation(categories, people, number_people_wanted,
                                                                  check_same_address, households)

    # Start by finding some initial committees, guaranteed to cover every agent that can be covered by some committee
    committees: Set[FrozenSet[str]]  # set of feasible committees, add more over time
    covered_agents: FrozenSet[str]  # all agent ids for agents that can actually be included
    committees, covered_agents, new_output_lines = _generate_initial_committees(new_committee_model, agent_vars,
                                                                                3 * len(people))
    output_lines += new_output_lines

    # Over the course of the algorithm, the selection probabilities of more and more agents get fixed to a certain value
    fixed_probabilities: Dict[str, float] = {}

    reduction_counter = 0

    # The outer loop maximizes the minimum of all unfixed probabilities while satisfying the fixed probabilities.
    # In each iteration, at least one more probability is fixed, but often more than one.
    while len(fixed_probabilities) < len(people):
        print(f"Fixed {len(fixed_probabilities)}/{len(people)} probabilities.")

        dual_model, dual_agent_vars, dual_cap_var = _dual_leximin_stage(people, committees, fixed_probabilities)
        # In the inner loop, there is a column generation for maximizing the minimum of all unfixed probabilities
        while True:
            """The primal LP being solved by column generation, with a variable x_P for each feasible panel P:
            
            maximize z
            s.t.     Σ_{P : i ∈ P} x_P ≥ z                         ∀ i not in fixed_probabilities
                     Σ_{P : i ∈ P} x_P ≥ fixed_probabilities[i]    ∀ i in fixed_probabilities
                     Σ_P x_P ≤ 1                                   (This should be thought of as equality, and wlog.
                                                                   optimal solutions have equality, but simplifies dual)
                     x_P ≥ 0                                       ∀ P
                     
            We instead solve its dual linear program:
            minimize ŷ - Σ_{i in fixed_probabilities} fixed_probabilities[i] * yᵢ
            s.t.     Σ_{i ∈ P} yᵢ ≤ ŷ                              ∀ P
                     Σ_{i not in fixed_probabilities} yᵢ = 1
                     ŷ, yᵢ ≥ 0                                     ∀ i
            """
            dual_model.optimize()
            if dual_model.status != grb.GRB.OPTIMAL:
                # In theory, the LP is feasible in the first iterations, and we only add constraints (by fixing
                # probabilities) that preserve feasibility. Due to floating-point issues, however, it may happen that
                # Gurobi still cannot satisfy all the fixed probabilities in the primal (meaning that the dual will be
                # unbounded). In this case, we slightly relax the LP by slightly reducing all fixed probabilities.
                for agent in fixed_probabilities:
                    # Relax all fixed probabilities by a small constant
                    fixed_probabilities[agent] = max(0., fixed_probabilities[agent] - 0.0001)
                    dual_model, dual_agent_vars, dual_cap_var = _dual_leximin_stage(people, committees,
                                                                                    fixed_probabilities)
                print(dual_model.status, f"REDUCE PROBS for {reduction_counter}th time.")
                reduction_counter += 1
                continue

            # Find the panel P for which Σ_{i ∈ P} yᵢ is largest, i.e., for which Σ_{i ∈ P} yᵢ ≤ ŷ is tightest
            agent_weights = {person: agent_var.x for person, agent_var in dual_agent_vars.items()}
            new_committee_model.objective = mip.xsum(agent_weights[person] * agent_vars[person] for person in people)
            new_committee_model.optimize()
            new_set = _ilp_results_to_committee(agent_vars)  # panel P
            value = new_committee_model.objective_value  # Σ_{i ∈ P} yᵢ

            upper = dual_cap_var.x  # ŷ
            dual_obj = dual_model.objVal  # ŷ - Σ_{i in fixed_probabilities} fixed_probabilities[i] * yᵢ

            output_lines.append(_print(f"Maximin is at most {dual_obj - upper + value:.2%}, can do {dual_obj:.2%} with "
                                       f"{len(committees)} committees. Gap {value - upper:.2%}."))
            if value <= upper + EPS:
                # Within numeric tolerance, the panels in `committees` are enough to constrain the dual, i.e., they are
                # enough to support an optimal primal solution.
                for person, agent_weight in agent_weights.items():
                    if agent_weight > EPS and person not in fixed_probabilities:
                        # `agent_weight` is the dual variable yᵢ of the constraint "Σ_{P : i ∈ P} x_P ≥ z" for
                        # i = `person` in the primal LP. If yᵢ is positive, this means that the constraint must be
                        # binding in all optimal solutions [1], and we can fix `person`'s probability to the
                        # optimal value of the primal/dual LP.
                        # [1] Theorem 3.3 in: Renato Pelessoni. Some remarks on the use of the strict complementarity in
                        # checking coherence and extending coherent probabilities. 1998.
                        fixed_probabilities[person] = max(0, dual_obj)
                break
            else:
                # Given that Σ_{i ∈ P} yᵢ > ŷ, the current solution to `dual_model` is not yet a solution to the dual.
                # Thus, add the constraint for panel P and recurse.
                assert new_set not in committees
                committees.add(new_set)
                dual_model.addConstr(grb.quicksum(dual_agent_vars[id] for id in new_set) <= dual_cap_var)

    # The previous algorithm computed the leximin selection probabilities of each agent and a set of panels such that
    # the selection probabilities can be obtained by randomizing over these panels. Here, such a randomization is found.
    primal = grb.Model()
    # Variables for the output probabilities of the different panels
    committee_vars = [primal.addVar(vtype=grb.GRB.CONTINUOUS, lb=0.) for _ in committees]
    # To avoid numerical problems, we formally minimize the largest downward deviation from the fixed probabilities.
    eps = primal.addVar(vtype=grb.GRB.CONTINUOUS, lb=0.)
    primal.addConstr(grb.quicksum(committee_vars) == 1)  # Probabilities add up to 1
    for person, prob in fixed_probabilities.items():
        person_probability = grb.quicksum(comm_var for committee, comm_var in zip(committees, committee_vars)
                                          if person in committee)
        primal.addConstr(person_probability >= prob - eps)
    primal.setObjective(eps, grb.GRB.MINIMIZE)
    primal.optimize()

    # Bound variables between 0 and 1 and renormalize, because np.random.choice is sensitive to small deviations here
    probabilities = np.array([comm_var.x for comm_var in committee_vars]).clip(0, 1)
    probabilities = list(probabilities / sum(probabilities))

    return list(committees), probabilities, output_lines


def _find_maximin_primal(committees: List[FrozenSet[str]], covered_agents: FrozenSet[str]) -> List[float]:
    model = mip.Model(sense=mip.MAXIMIZE)

    committee_variables = [model.add_var(var_type=mip.CONTINUOUS, lb=0., ub=1.) for _ in committees]
    model.add_constr(mip.xsum(committee_variables) == 1)
    agent_panel_variables = {id: [] for id in covered_agents}
    for committee, var in zip(committees, committee_variables):
        for id in committee:
            if id in covered_agents:
                agent_panel_variables[id].append(var)

    lower = model.add_var(var_type=mip.CONTINUOUS, lb=0., ub=1.)

    for agent_variables in agent_panel_variables.values():
        model.add_constr(lower <= mip.xsum(agent_variables))
    model.objective = lower
    model.optimize()

    probabilities = [var.x for var in committee_variables]
    probabilities = [max(p, 0) for p in probabilities]
    sum_probabilities = sum(probabilities)
    probabilities = [p / sum_probabilities for p in probabilities]
    return probabilities


def find_distribution_maximin(categories: Dict[str, Dict[str, Dict[str, int]]], people: Dict[str, Dict[str, str]],
                              columns_data: Dict[str, Dict[str, str]], number_people_wanted: int,
                              check_same_address: bool, check_same_address_columns: List[str]) \
        -> Tuple[List[FrozenSet[str]], List[float], List[str]]:
    """Find a distribution over feasible committees that maximizes the minimum probability of an agent being selected.

    Arguments follow the pattern of `find_random_sample`.

    Returns:
        (committees, probabilities, output_lines)
        `committees` is a list of feasible committees, where each committee is represented by a frozen set of included
            agent ids.
        `probabilities` is a list of probabilities of equal length, describing the probability with which each committee
            should be selected.
        `output_lines` is a list of debug strings.
    """
    output_lines = [_print("Using maximin algorithm.")]

    if check_same_address:
        households = _compute_households(people, columns_data, check_same_address_columns)
    else:
        households = None

    # Set up an ILP `new_committee_model` that can be used for discovering new feasible committees maximizing some
    # sum of weights over the agents.
    new_committee_model, agent_vars = _setup_committee_generation(categories, people, number_people_wanted,
                                                                  check_same_address, households)

    # Start by finding some initial committees, guaranteed to cover every agent that can be covered by some committee
    committees: Set[FrozenSet[str]]  # set of feasible committees, add more over time
    covered_agents: FrozenSet[str]  # all agent ids for agents that can actually be included
    committees, covered_agents, new_output_lines = _generate_initial_committees(new_committee_model, agent_vars,
                                                                                len(people))
    output_lines += new_output_lines

    # The incremental model is an LP with a variable y_e for each entitlement e and one more variable z.
    # For an agent i, let e(i) denote her entitlement. Then, the LP is:
    #
    # minimize  z
    # s.t.      Σ_{i ∈ B} y_{e(i)} ≤ z   ∀ feasible committees B (*)
    #           Σ_e y_e = 1
    #           y_e ≥ 0                  ∀ e
    #
    # At any point in time, constraint (*) is only enforced for the committees in `committees`. By linear-programming
    # duality, if the optimal solution with these reduced constraints satisfies all possible constraints, the committees
    # in `committees` are enough to find the maximin distribution among them.
    incremental_model = mip.Model(sense=mip.MINIMIZE)
    incremental_model.verbose = debug

    upper_bound = incremental_model.add_var(var_type=mip.CONTINUOUS, lb=0., ub=mip.INF)  # variable z
    # variables y_e
    incr_agent_vars = {id: incremental_model.add_var(var_type=mip.CONTINUOUS, lb=0., ub=1.) for id in covered_agents}

    # Σ_e y_e = 1
    incremental_model.add_constr(mip.xsum(incr_agent_vars.values()) == 1)
    # minimize z
    incremental_model.objective = upper_bound

    for committee in committees:
        committee_sum = mip.xsum([incr_agent_vars[id] for id in committee])
        # Σ_{i ∈ B} y_{e(i)} ≤ z   ∀ B ∈ `committees`
        incremental_model.add_constr(committee_sum <= upper_bound)

    while True:
        status = incremental_model.optimize()
        assert status == mip.OptimizationStatus.OPTIMAL

        entitlement_weights = {id: incr_agent_vars[id].x for id in covered_agents}  # currently optimal values for y_e
        upper = upper_bound.x  # currently optimal value for z

        # For these fixed y_e, find the feasible committee B with maximal Σ_{i ∈ B} y_{e(i)}.
        new_committee_model.objective = mip.xsum(entitlement_weights[id] * agent_vars[id] for id in covered_agents)
        new_committee_model.optimize()
        new_set = _ilp_results_to_committee(agent_vars)
        value = sum(entitlement_weights[id] for id in new_set)

        output_lines.append(_print(f"Maximin is at most {value:.2%}, can do {upper:.2%} with {len(committees)} "
                                   f"committees. Gap {value - upper:.2%}{'≤' if value - upper <= EPS else '>'}{EPS:%}."))
        if value <= upper + EPS:
            # No feasible committee B violates Σ_{i ∈ B} y_{e(i)} ≤ z (at least up to EPS, to prevent rounding errors).
            # Thus, we have enough committees.
            committee_list = list(committees)
            probabilities = _find_maximin_primal(committee_list, covered_agents)
            return committee_list, probabilities, output_lines
        else:
            # Some committee B violates Σ_{i ∈ B} y_{e(i)} ≤ z. We add B to `committees` and recurse.
            assert new_set not in committees
            committees.add(new_set)
            incremental_model.add_constr(mip.xsum(incr_agent_vars[id] for id in new_set) <= upper_bound)

            # Heuristic for better speed in practice:
            # Because optimizing `incremental_model` takes a long time, we would like to get multiple committees out
            # of a single run of `incremental_model`. Rather than reoptimizing for optimal y_e and z, we find some
            # feasible values y_e and z by modifying the old solution.
            # This heuristic only adds more committees, and does not influence correctness.
            counter = 0
            for _ in range(10):
                # scale down the y_{e(i)} for i ∈ `new_set` to make Σ_{i ∈ `new_set`} y_{e(i)} ≤ z true.
                for id in new_set:
                    entitlement_weights[id] *= upper / value
                # This will change Σ_e y_e to be less than 1. We rescale the y_e and z.
                sum_weights = sum(entitlement_weights.values())
                if sum_weights < EPS:
                    break
                for id in entitlement_weights:
                    entitlement_weights[id] /= sum_weights
                upper /= sum_weights

                new_committee_model.objective = mip.xsum(entitlement_weights[id] * agent_vars[id]
                                                         for id in covered_agents)
                new_committee_model.optimize()
                new_set = _ilp_results_to_committee(agent_vars)
                value = sum(entitlement_weights[id] for id in new_set)
                if value <= upper + EPS or new_set in committees:
                    break
                else:
                    committees.add(new_set)
                    incremental_model.add_constr(mip.xsum(incr_agent_vars[id] for id in new_set) <= upper_bound)
                counter += 1
            if counter > 0:
                print(f"Heuristic successfully generated {counter} additional committees.")


def _define_entitlements(covered_agents: FrozenSet[str]) -> Tuple[List[str], Dict[str, int]]:
    entitlements = list(covered_agents)
    contributes_to_entitlement = {}
    for id in covered_agents:
        contributes_to_entitlement[id] = entitlements.index(id)

    return entitlements, contributes_to_entitlement


def _committees_to_matrix(committees: List[FrozenSet[str]], entitlements: list,
                          contributes_to_entitlement: Dict[str, int]) -> np.ndarray:
    columns = []
    for committee in committees:
        column = [0 for _ in entitlements]
        for id in committee:
            column[contributes_to_entitlement[id]] += 1
        columns.append(np.array(column))
    return np.column_stack(columns)


def find_distribution_nash(categories: Dict[str, Dict[str, Dict[str, int]]], people: Dict[str, Dict[str, str]],
                           columns_data: Dict[str, Dict[str, str]], number_people_wanted: int, check_same_address: bool,
                           check_same_address_columns: List[str]) \
        -> Tuple[List[FrozenSet[str]], List[float], List[str]]:
    """Find a distribution over feasible committees that maximizes the so-called Nash welfare, i.e., the product of
    selection probabilities over all persons.

    Arguments follow the pattern of `find_random_sample`.

    Returns:
        (committees, probabilities, output_lines)
        `committees` is a list of feasible committees, where each committee is represented by a frozen set of included
            agent ids.
        `probabilities` is a list of probabilities of equal length, describing the probability with which each committee
            should be selected.
        `output_lines` is a list of debug strings.

    The following gives more details about the algorithm:
    Instead of directly maximizing the product of selection probabilities Πᵢ pᵢ, we equivalently maximize
    log(Πᵢ pᵢ) = Σᵢ log(pᵢ). If some person/household i is not included in any feasible committee, their pᵢ is 0, and
    this sum is -∞. We will then try to maximize Σᵢ log(pᵢ) where i is restricted to range over persons/households that
    can possibly be included.
    """
    output_lines = ["Using Nash algorithm."]

    if check_same_address:
        households = _compute_households(people, columns_data, check_same_address_columns)
    else:
        households = None

    # `new_committee_model` is an integer linear program (ILP) used for discovering new feasible committees.
    # We will use it many times, putting different weights on the inclusion of different agents to find many feasible
    # committees.
    new_committee_model, agent_vars = _setup_committee_generation(categories, people, number_people_wanted,
                                                                  check_same_address, households)

    # Start by finding committees including every agent, and learn which agents cannot possibly be included.
    committees: List[FrozenSet[str]]  # set of feasible committees, add more over time
    covered_agents: FrozenSet[str]  # all agent ids for agents that can actually be included
    committee_set, covered_agents, new_output_lines = _generate_initial_committees(new_committee_model, agent_vars,
                                                                                   2 * len(people))
    committees = list(committee_set)
    output_lines += new_output_lines

    # Map the covered agents to indices in a list for easier matrix representation.
    entitlements: List[str]
    contributes_to_entitlement: Dict[str, int]  # for id of a covered agent, the corresponding index in `entitlements`
    entitlements, contributes_to_entitlement = _define_entitlements(covered_agents)

    # Now, the algorithm proceeds iteratively. First, it finds probabilities for the committees already present in
    # `committees` that maximize the sum of logarithms. Then, reusing the old ILP, it finds the feasible committee
    # (possibly outside of `committees`) such that the partial derivative of the sum of logarithms with respect to the
    # probability of outputting this committee is maximal. If this partial derivative is less than the maximal partial
    # derivative of any committee already in `committees`, the Karush-Kuhn-Tucker conditions (which are sufficient in
    # this case) imply that the distribution is optimal even with all other committees receiving probability 0.
    start_lambdas = [1 / len(committees) for _ in committees]
    while True:
        lambdas = cp.Variable(len(committees))  # probability of outputting a specific committee
        lambdas.value = start_lambdas
        # A is a binary matrix, whose (i,j)th entry indicates whether agent `feasible_agents[i]`
        matrix = _committees_to_matrix(committees, entitlements, contributes_to_entitlement)
        assert matrix.shape == (len(entitlements), len(committees))

        objective = cp.Maximize(cp.sum(cp.log(matrix * lambdas)))
        constraints = [0 <= lambdas, sum(lambdas) == 1]
        problem = cp.Problem(objective, constraints)
        # TODO: test relative performance of both solvers, see whether warm_start helps.
        try:
            nash_welfare = problem.solve(solver=cp.SCS, warm_start=True)
        except cp.SolverError:
            # At least the ECOS solver in cvxpy crashes sometimes (numerical instabilities?). In this case, try another
            # solver. But hope that SCS is more stable.
            output_lines.append(_print("Had to switch to ECOS solver."))
            nash_welfare = problem.solve(solver=cp.ECOS, warm_start=True)
        scaled_welfare = nash_welfare - len(entitlements) * log(number_people_wanted / len(entitlements))
        output_lines.append(_print(f"Scaled Nash welfare is now: {scaled_welfare}."))

        assert lambdas.value.shape == (len(committees),)
        entitled_utilities = matrix.dot(lambdas.value)
        assert entitled_utilities.shape == (len(entitlements),)
        assert (entitled_utilities > EPS2).all()
        entitled_reciprocals = 1 / entitled_utilities
        assert entitled_reciprocals.shape == (len(entitlements),)
        differentials = entitled_reciprocals.dot(matrix)
        assert differentials.shape == (len(committees),)

        obj = []
        for id in covered_agents:
            obj.append(entitled_reciprocals[contributes_to_entitlement[id]] * agent_vars[id])
        new_committee_model.objective = mip.xsum(obj)
        new_committee_model.optimize()

        new_set = _ilp_results_to_committee(agent_vars)
        value = sum(entitled_reciprocals[contributes_to_entitlement[id]] for id in new_set)
        if value <= differentials.max() + EPS_NASH:
            probabilities = np.array(lambdas.value).clip(0, 1)
            probabilities = list(probabilities / sum(probabilities))
            # TODO: filter 0-probability committees?
            return committees, probabilities, output_lines
        else:
            print(value, differentials.max(), value - differentials.max())
            assert new_set not in committees
            committees.append(new_set)
            start_lambdas = np.array(lambdas.value).resize(len(committees))


###################################
#
# main algorithm call
#
###################################


def run_stratification(categories, people, columns_data, number_people_wanted, min_max_people, settings: Settings,
                       test_selection, number_selections):
    # First check if numbers in cat file and to select make sense
    for mkey, mvalue in min_max_people.items():
        if settings.selection_algorithm == "legacy" and (  # For other algorithms, quotas are analyzed later
                number_people_wanted < mvalue["min"] or number_people_wanted > mvalue["max"]):
            error_msg = (
                "The number of people to select ({}) is out of the range of the numbers of people "
                "in one of the {} categories. It should be within [{}, {}].".format(
                    number_people_wanted, mkey, mvalue["min"], mvalue["max"]
                )
            )
            return False, 0, {}, [error_msg]
    # set the random seed if it is NOT zero
    if settings.random_number_seed:
        random.seed(settings.random_number_seed)

    tries = 0
    success = False
    output_lines = []
    if test_selection:
        output_lines.append(
            "<b style='color: red'>WARNING: Panel is not selected at random! Only use for testing!</b><br>")
    output_lines.append("<b>Initial: (selected = 0)</b>")
    categories_working = {}
    people_selected = {}
    while not success and tries < settings.max_attempts:
        people_selected = {}
        people_working = copy.deepcopy(people)
        categories_working = copy.deepcopy(categories)
        if tries == 0:
            new_output_lines = print_category_info(categories_working, people, people_selected, number_people_wanted)
            output_lines += new_output_lines

        output_lines.append("<b>Trial number: {}</b>".format(tries))
        try:
            people_selected, new_output_lines = find_random_sample(categories_working, people_working, columns_data,
                                                                   number_people_wanted, settings.check_same_address,
                                                                   settings.check_same_address_columns,
                                                                   settings.selection_algorithm,
                                                                   test_selection,
                                                                   number_selections)
            output_lines += new_output_lines
            # check we have met targets needed in all cats
            # note this only works for number_selections = 1
            new_output_lines = print_category_info(categories_working, people, people_selected, number_people_wanted)
            success, check_output_lines = check_category_selected(categories_working, people, people_selected, number_selections)
            if success:
                output_lines.append("<b>SUCCESS!!</b> Final:")
                output_lines += (new_output_lines + check_output_lines)
        except ValueError as err:
            output_lines.append(str(err))
            break
        except InfeasibleQuotasError as err:
            output_lines += err.output
            break
        except InfeasibleQuotasCantRelaxError as err:
            output_lines.append(err.message)
            break
        except SelectionError as serr:
            output_lines.append("Failed: Selection Error thrown: " + serr.msg)
        tries += 1
    if not success:
        output_lines.append("Failed {} times... gave up.".format(tries))
    return success, people_selected, output_lines
