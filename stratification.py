"""
    Python script to do a stratified, random selection from respondents to random mail out

    Version 0.7  (13 May 2019) - Now compatible with python3 ...

    written by Brett Hennig bsh@sortitionfoundation.org

    TO DO/limitations:
        - could make various things as command line args
        - could make is find multiple solutions and pick the best?

"""
import copy
import csv
import random
import typing

#######

# the number of people in each category must be (more or less) the total number of people to be selected
total_number_people_wanted = 22

######

# data columns in spreadsheet to keep and print in output file (as well as stratification columns of course):
# WARNING: primary_address1 and primary_zip are used in the code to check same addresses!
columns_to_keep = [
    "first_name",
    "last_name",
    "email",
    "mobile_number",
    "primary_address1",
    "primary_address2",
    "primary_city",
    "primary_zip",
]
# do we check if people are from the same address and, if so, make sure only one is selected?
check_same_address = True
# this (unique) column must be in the people CSV file
id_column = "nationbuilder_id"

number_people_example_file = 150

max_attempts = 100
# 0 means no debug message, higher number (could) mean more messages
debug = 0


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
def create_readable_sample_file(categories, people_file: typing.TextIO):
    example_people_writer = csv.writer(
        people_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
    )
    cat_keys = categories.keys()
    example_people_writer.writerow([id_column] + columns_to_keep + list(cat_keys))
    for x in range(number_people_example_file):
        row = ["p{}".format(x)]
        for col in columns_to_keep:
            row.append(col + str(x))
        for cat_key, cats in categories.items():
            random_cat_value = random.choice(list(cats.keys()))
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


# selected = True means we are deleting because they have bene chosen,
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
def delete_person(categories, people, pkey, columns_data):
    output_lines = []
    # recalculate all category values that this person was in
    person = people[pkey]
    really_delete_person(categories, people, pkey, True)
    # check if there are other people at the same address - if so, remove them!
    if check_same_address:
        primary_address1 = columns_data[pkey]["primary_address1"]
        primary_zip = columns_data[pkey]["primary_zip"]
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
                # so delete this person
                really_delete_person(categories, people, compare_key, False)
    # then check if any cats of selected person is (was) in are full
    for (pcat, pval) in person.items():
        cat_item = categories[pcat][pval]
        if cat_item["selected"] == cat_item["max"]:
            output_lines += delete_all_in_cat(categories, people, pcat, pval)
    return output_lines


# read in categories - a dict of dicts of dicts...
def read_in_cats(category_file: typing.TextIO):
    categories = {}
    cat_file = csv.DictReader(category_file)
    for row in cat_file:  # must convert min/max to ints
        if row["category"] in categories:  # must convert min/max to ints
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
    return categories


# read in people and calculate how many people in each category in database
def init_categories_people(people_file: typing.TextIO, categories):
    people = {}
    columns_data = {}
    people_data = csv.DictReader(people_file)
    cat_keys = categories.keys()
    for row in people_data:
        key = row[id_column]
        value = {}
        for cat in cat_keys:
            # print(cat, row[cat])
            # COULD check for input errors here - if it's not in the list of category values...
            value.update({cat: row[cat]})
            categories[cat][row[cat]]["remaining"] += 1
        people.update({key: value})
        # this is address, name etc that we need to keep for output file
        data_value = {}
        for col in columns_to_keep:
            data_value[col] = row[col]
        columns_data.update({key: data_value})
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


def print_category_selected(categories):
    report_lines = []
    for cat_key, cats in categories.items():  # print out how many in each
        for cat, cat_item in cats.items():
            percent_selected = round(
                cat_item["selected"] * 100 / float(total_number_people_wanted), 2
            )
            report_lines.append(
                "{}: {} ({}%)  (Want [{}, {}] Remaining = {})".format(
                    cat,
                    cat_item["selected"],
                    percent_selected,
                    cat_item["min"],
                    cat_item["max"],
                    cat_item["remaining"],
                )
            )
    return report_lines


def check_min_cats(categories):
    output_msg = []
    got_min = True
    for cat_key, cats in categories.items():
        for cat, cat_item in cats.items():
            if cat_item["selected"] < cat_item["min"]:
                got_min = False
                output_msg = [ "Failed to get minimum in category: {}".format( cat ) ]
    return got_min, output_msg


# main algorithm to try to find a random sample
def find_random_sample(categories, people, columns_data):
    output_lines = []
    people_selected = {}
    for count in range(total_number_people_wanted):
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
                    output_lines += delete_person(categories, people, pkey, columns_data)
                    break
        if count < (total_number_people_wanted - 1) and len(people) == 0:
            raise SelectionError("Fail! We've run out of people...")
    return people_selected, output_lines


###################################
#
# main program start
#
###################################


def run_stratification(categories, people, columns_data):
    success = False
    tries = 0
    output_lines = [ "Initial: (selected/remaining)" ]
    while not success and tries < max_attempts:
        people_selected = {}
        new_output_lines = []
        people_working = copy.deepcopy(people)
        categories_working = copy.deepcopy(categories)
        if tries == 0:
            output_lines += print_category_selected(categories_working)
        output_lines.append( "Trial number: " + str(tries) )
        try:
            people_selected, new_output_lines = find_random_sample(categories_working, people_working, columns_data)
            output_lines += new_output_lines
            # check we have reached minimum needed in all cats
            check_min_cat, new_output_lines = check_min_cats(categories_working)
            if check_min_cat:
                output_lines.append( "SUCCESS!!" )
                success = True
            else:
                output_lines += new_output_lines
        except SelectionError as serr:
            output_lines.append( "Failed: Selection Error thrown: " + serr.msg )
        tries += 1
    return success, tries, people_selected, output_lines

# Actually useful to also write to a file all those who are NOT selected for later selection if people pull out etc
def write_selected_people_to_file(people, people_selected, categories, columns_data, selected_file: typing.TextIO, remaining_file):
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
        del people[pkey]
        
    people_remaining_writer = csv.writer(
        remaining_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
    )
    people_remaining_writer.writerow(
        [id_column] + columns_to_keep + list(categories.keys())
    )
    for pkey, person in people.items():
        row = [pkey]
        for col in columns_to_keep:
            row.append(columns_data[pkey][col])
        row += person.values()
        people_remaining_writer.writerow(row)
