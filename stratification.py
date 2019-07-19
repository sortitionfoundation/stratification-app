"""
    Python (3) script to do a stratified, random selection from respondents to random mail out

    written by Brett Hennig bsh [AT] sortitionfoundation.org

"""
import copy
import csv
import random
import typing

# 0 means no debug message, higher number (could) mean more messages
debug = 0


def initialise_settings():
    with open("sf_stratification_settings.txt", "r") as settings_file:
        id_column = settings_file.readline().strip()
        id_column = id_column[id_column.find(":")+1:].strip()
        check_same_address_str = settings_file.readline().strip()
        check_same_address_str = check_same_address_str[check_same_address_str.find(":")+1:].strip()
        if check_same_address_str == "True" or check_same_address_str == "true" or check_same_address_str == "T":
            check_same_address = True
        else:
            check_same_address = False
        max_attempts_str = settings_file.readline().strip()
        max_attempts_str = max_attempts_str[max_attempts_str.find(":")+1:].strip()
        max_attempts = int(max_attempts_str)
        columns_to_keep = []
        # read column heading line
        col_header = settings_file.readline().strip()
        if col_header != "columns_to_keep:":
            print("Error in reading settings file - no columns_to_keep line found where it should be")
        for next_line in settings_file:
            next_line = next_line.strip()
            if next_line != "":
                columns_to_keep.append(next_line)
    '''
    # this (unique) column must be in the people CSV file
    id_column = "nationbuilder_id"
    # data columns in people spreadsheet to keep and print in output file (as well as stratification/category columns of course):
    # WARNING: primary_address1 and primary_zip are used in the code to check same addresses (see below)!
    columns_to_keep = [
        "first_name",
        "last_name",
        "email",
        "mobile_number",
        "primary_address1",
        "primary_address2",
        "primary_city",
        "primary_zip",
        "Age"
    ]
    # do we check if people are from the same address and, if so, make sure only one is selected?
    check_same_address = True
    # How many times do we try to find a solution before giving up?
    max_attempts = 100
    '''
    return id_column, columns_to_keep, check_same_address, max_attempts


# categories is a dict of dicts of dicts... like:
#   categories = { 'gender' : gender, 'age' : age, 'geo' : geo, 'socio' : socio }
# with each category a dict of possible values with set data, like:
#     gender = { 'Gender: Male' : { 'min' : 20, 'max' : 24, 'selected' : 0, 'remaining' : 0 },
#                'Gender: Female' : { 'min' : 21, 'max' : 25, 'selected' : 0, 'remaining' : 0 }
# etc         }


# class for throwing error/fail exceptions
class SelectionError(Exception):
    def __init__(self, message):
        self.msg = message


# create READABLE example file of people
def create_readable_sample_file(id_column, categories, columns_to_keep, people_file: typing.TextIO, number_people_example_file):
    example_people_writer = csv.writer(
        people_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
    )
    cat_keys = categories.keys()
    example_people_writer.writerow([id_column] + columns_to_keep + list(cat_keys))
    for x in range(number_people_example_file):
        row = ["p{}".format(x)]
        for col in columns_to_keep:
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
def delete_all_in_cat(categories, people, cat, cat_value):
    people_to_delete = []
    for pkey, person in people.items():
        if person[cat] == cat_value:
            people_to_delete.append(pkey)
            for pcat, pval in person.items():
                cat_item = categories[pcat][pval]
                cat_item["remaining"] -= 1
                if cat_item["remaining"] == 0 and cat_item["selected"] < cat_item["min"]:
                    raise SelectionError(
                        "FAIL in delete_all_in_cat: no one/not enough left in " + pval
                    )
    for p in people_to_delete:
        del people[p]
    return [
        "Category {} full - deleted {}, {} left.".format(
            cat_value, len(people_to_delete), len(people)
        )
    ]


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


# lucky person has been selected - delete person from DB
def delete_person(categories, people, pkey, columns_data, check_same_address):
    output_lines = []
    # recalculate all category values that this person was in
    person = people[pkey]
    really_delete_person(categories, people, pkey, True)
    # check if there are other people at the same address - if so, remove them!
    if check_same_address:
        primary_address1 = columns_data[pkey]["primary_address1"]
        primary_zip = columns_data[pkey]["primary_zip"]
        # there may be multiple people to delete, and deleting them as we go gives an error
        people_to_delete = []
        for compare_key in people.keys():
            if (
                primary_address1 == columns_data[compare_key]["primary_address1"]
                and primary_zip == columns_data[compare_key]["primary_zip"]
            ):
                # found same address
                output_lines += [
                    "Found someone with the same address as a selected person,"
                    " so deleting him/her. Address: {} , {}".format(primary_address1, primary_zip)
                ]
                people_to_delete.append(compare_key)
        # then delete this/these people at the same address
        for del_person_key in people_to_delete:
            really_delete_person(categories, people, del_person_key, False)
    # then check if any cats of selected person is (was) in are full
    for (pcat, pval) in person.items():
        cat_item = categories[pcat][pval]
        if cat_item["selected"] == cat_item["max"]:
            output_lines += delete_all_in_cat(categories, people, pcat, pval)
    return output_lines


# read in categories - a dict of dicts of dicts...
def read_in_cats(category_file: typing.TextIO):
    categories = {}
    # to keep track of number in cats - number people selected MUST be between these limits in every cat...
    min_max_people_cats = {}
    cat_file = csv.DictReader(category_file)
    for row in cat_file:  # must convert min/max to ints
        if row["category"] in categories:  # must convert min/max to ints
            min_max_people_cats[row["category"]]["min"] += int(row["min"])
            min_max_people_cats[row["category"]]["max"] += int(row["max"])
            categories[row["category"]].update(
                {
                    row["name"]: {
                        "min": int(row["min"]),
                        "max": int(row["max"]),
                        "selected": 0,
                        "remaining": 0,
                    }
                }
            )
        else:
            min_max_people_cats.update(
                {
                    row["category"]: {
                        "min": int(row["min"]),
                        "max": int(row["max"])
                    }
                }
            )
            categories.update(
                {
                    row["category"]: {
                        row["name"]: {
                            "min": int(row["min"]),
                            "max": int(row["max"]),
                            "selected": 0,
                            "remaining": 0,
                        }
                    }
                }
            )
    return categories, min_max_people_cats


# read in people and calculate how many people in each category in database
def init_categories_people(people_file: typing.TextIO, id_column, categories, columns_to_keep):
    people = {}
    columns_data = {}
    people_data = csv.DictReader(people_file)
    for row in people_data:
        pkey = row[id_column]
        value = {}
        for cat_key, cats in categories.items():
            # check for input errors here - if it's not in the list of category values...
            if row[cat_key] not in cats:
                raise Exception(
                    "ERROR reading in people (init_categories_people): Person (id = {}) has value {} not in category {}".format(pkey, row[cat_key], cat_key)
                )
            value.update({cat_key: row[cat_key]})
            categories[cat_key][row[cat_key]]["remaining"] += 1
        people.update({pkey: value})
        # this is address, name etc that we need to keep for output file
        data_value = {}
        for col in columns_to_keep:
            data_value[col] = row[col]
        columns_data.update({pkey: data_value})
    # check if any cat[max] is set to zero... if so delete everyone with that cat...
    # could then check if anyone left...
    # for person in people.items():
    #     for pcat, pval in person.items(): #then check if any cats of selected person is (was) in are full
    #         cat_item = categories[pcat][pval]
    #         if cat_item['max'] == 0:
    #             delete_all_in_cat(categories, people, pcat, pval)
    return people, columns_data


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


def print_category_selected(categories, number_people_wanted):
    report_msg = "<table border='1' cellpadding='5'>"
    report_msg += "<tr><th colspan='2'>Category</th><th>Selected</th><th>Want</th><th>Remaining</th></tr>"
    for cat_key, cats in categories.items():  # print out how many in each
        for cat, cat_item in cats.items():
            percent_selected = round(
                cat_item["selected"] * 100 / float(number_people_wanted), 2
            )
            report_msg += "<tr><td>{}</td><td>{}</td><td>{} ({}%)</td><td>[{},{}]</td><td>{}</td></tr>".format(
                cat_key,
                cat,
                cat_item["selected"],
                percent_selected,
                cat_item["min"],
                cat_item["max"],
                cat_item["remaining"],
            )
    report_msg += "</table>"
    return [report_msg]


def check_min_cats(categories):
    output_msg = []
    got_min = True
    for cat_key, cats in categories.items():
        for cat, cat_item in cats.items():
            if cat_item["selected"] < cat_item["min"]:
                got_min = False
                output_msg = ["Failed to get minimum in category: {}".format(cat)]
    return got_min, output_msg


# main algorithm to try to find a random sample
def find_random_sample(categories, people, columns_data, number_people_wanted, check_same_address):
    output_lines = []
    people_selected = {}
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
                    people_selected.update({pkey: pvalue})
                    output_lines += delete_person(categories, people, pkey, columns_data, check_same_address)
                    break
        if count < (number_people_wanted - 1) and len(people) == 0:
            raise SelectionError("Fail! We've run out of people...")
    return people_selected, output_lines


def get_selection_number_range(min_max_people_cats):
    max_values = [v['max'] for v in min_max_people_cats.values()]
    maximum = min(max_values)
    min_values = [v['min'] for v in min_max_people_cats.values()]
    minimum = max(min_values)
    return minimum, maximum


###################################
#
# main program start
#
###################################


def run_stratification(categories, people, columns_data, number_people_wanted, min_max_people_cats, max_attempts, check_same_address):
    # First check if numbers in cat file and to select make sense
    for mkey, mvalue in min_max_people_cats.items():
        if number_people_wanted < mvalue["min"] or number_people_wanted > mvalue["max"]:
            error_msg = (
                "The number of people to select ({}) is out of the range of the numbers of people "
                "in one of the {} categories. It should be within [{}, {}].".format(
                    number_people_wanted, mkey, mvalue["min"], mvalue["max"]
                )
            )
            return False, 0, {}, [error_msg]
    success = False
    tries = 0
    output_lines = ["<b>Initial: (selected = 0/remaining = total people in category)</b>"]
    while not success and tries < max_attempts:
        people_selected = {}
        new_output_lines = []
        people_working = copy.deepcopy(people)
        categories_working = copy.deepcopy(categories)
        if tries == 0:
            output_lines += print_category_selected(categories_working, number_people_wanted)
        output_lines.append("<b>Trial number: {}</b>".format(tries))
        try:
            people_selected, new_output_lines = find_random_sample(categories_working, people_working, columns_data, number_people_wanted, check_same_address)
            output_lines += new_output_lines
            # check we have reached minimum needed in all cats
            check_min_cat, new_output_lines = check_min_cats(categories_working)
            if check_min_cat:
                output_lines.append("<b>SUCCESS!!</b>")
                success = True
            else:
                output_lines += new_output_lines
        except SelectionError as serr:
            output_lines.append("Failed: Selection Error thrown: " + serr.msg)
        tries += 1
    output_lines.append("Final:")
    output_lines += print_category_selected(categories_working, number_people_wanted)
    if success:
        output_lines.append("We tried {} time(s).".format(tries))
        output_lines.append("Count = {} people selected".format(len(people_selected)))  # , people_selected
    else:
        output_lines.append("Failed {} times... gave up.".format(tries))
    return success, tries, people_selected, output_lines


# Actually useful to also write to a file all those who are NOT selected for later selection if people pull out etc
def write_selected_people_to_file(people, people_selected, id_column, categories, columns_to_keep, columns_data, selected_file: typing.TextIO, remaining_file):
    people_working = copy.deepcopy(people)
    people_selected_writer = csv.writer(
        selected_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
    )
    people_selected_writer.writerow(
        [id_column] + columns_to_keep + list(categories.keys())
    )
    for pkey, person in people_selected.items():
        row = [pkey]
        for col in columns_to_keep:
            row.append(columns_data[pkey][col])
        row += person.values()
        people_selected_writer.writerow(row)
        del people_working[pkey]

    people_remaining_writer = csv.writer(
        remaining_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
    )
    people_remaining_writer.writerow(
        [id_column] + columns_to_keep + list(categories.keys())
    )
    for pkey, person in people_working.items():
        row = [pkey]
        for col in columns_to_keep:
            row.append(columns_data[pkey][col])
        row += person.values()
        people_remaining_writer.writerow(row)
