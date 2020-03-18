"""
    Python (3) script to do a stratified, random selection from respondents to random mail out

    written by Brett Hennig bsh [AT] sortitionfoundation.org
    contributions by Paul Gölz pgoelz (AT) cs.cmu.edu

"""
import copy
import csv
from math import log
import random
import typing
from typing import Dict, List, Tuple, FrozenSet, Optional
from pathlib import Path

import cvxpy as cp
import mip
import numpy as np
import toml

# 0 means no debug message, higher number (could) mean more messages
debug = 0
# Warning: "name" value is hardcoded somewhere below :-)
category_file_field_names = ["category", "name", "min", "max"]
# numerical deviation accepted as equality when dealing with solvers
EPS = 0.05  # TODO: Find good value
EPS2 = 0.0000001

DEFAULT_SETTINGS = """
# #####################################################################
#
# IF YOU EDIT THIS FILE YOU NEED TO RESTART THE APPLICATION
#
# #####################################################################

# this is written in TOML - https://github.com/toml-lang/toml

id_column = "nationbuilder_id"

# if check_same_address is true, then no 2 people from the same address will be selected
# the comparison is between TWO fields listed here, which MUST also be below in columns_to_keep
check_same_address = true
check_same_address_columns = [
    "primary_address1",
    "primary_zip"
]
max_attempts = 100
columns_to_keep = [
    "first_name",
    "last_name",
    "email",
    "mobile_number",
    "primary_address1",
    "primary_address2",
    "primary_city",
    "primary_zip",
    "age"
]

# selection_algorithm can either be "legacy", "maximin", or "nash"
selection_algorithm = "nash"
# If false, maximin and nash algorithms aim to balance each person's probability. If true, they instead aim to give
# each household the same probability of having some member participate.
fair_to_households = false
"""


class NoSettingsFile(Exception):
    pass


class Settings():

    def __init__(self, id_column, columns_to_keep, check_same_address, check_same_address_columns, max_attempts,
                 selection_algorithm, fair_to_households):
        try:
            assert(isinstance(id_column, str))
            assert(isinstance(columns_to_keep, list))
            # if they have no personal data this could actually be empty
            # assert(len(columns_to_keep) > 0)
            for column in columns_to_keep:
                assert(isinstance(column, str))
            assert(isinstance(check_same_address, bool))
            assert(isinstance(check_same_address_columns, list))
			# this could be empty
            #assert(len(check_same_address_columns) == 2)
            for column in check_same_address_columns:
                assert(isinstance(column, str))
            assert(isinstance(max_attempts, int))
            assert(selection_algorithm in ["legacy", "maximin", "nash"])
            assert(isinstance(fair_to_households, bool))
        except AssertionError as error:
            print(error)

        self.id_column = id_column
        self.columns_to_keep = columns_to_keep
        self.check_same_address = check_same_address
        self.check_same_address_columns = check_same_address_columns
        self.max_attempts = max_attempts
        self.selection_algorithm = selection_algorithm
        self.fair_to_households = fair_to_households

    @classmethod
    def load_from_file(cls):
        message = ""
        settings_file_path = Path.home() / "sf_stratification_settings.toml"
        if not settings_file_path.is_file():
            with open(settings_file_path, "w") as settings_file:
                settings_file.write(DEFAULT_SETTINGS)
            message = "Wrote default settings to '{}' - if editing is required, restart this app.".format(
                settings_file_path.absolute()
            )
        with open(settings_file_path, "r") as settings_file:
            settings = toml.load(settings_file)
        return cls(
            settings['id_column'],
            settings['columns_to_keep'],
            settings['check_same_address'],
            settings['check_same_address_columns'],
            settings['max_attempts'],
            settings['selection_algorithm'],
            settings['fair_to_households']
        ), message


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


def get_people_at_same_address(people, pkey, columns_data, check_same_address_columns):
    # primary_address1 = columns_data[pkey]["primary_address1"]
    # primary_zip = columns_data[pkey]["primary_zip"]
    primary_address1 = columns_data[pkey][check_same_address_columns[0]]
    primary_zip = columns_data[pkey][check_same_address_columns[1]]
    # there may be multiple people to delete, and deleting them as we go gives an error
    people_to_delete = []
    output_lines = []
    for compare_key in people.keys():
        if (
            # primary_address1 == columns_data[compare_key]["primary_address1"]
            # and primary_zip == columns_data[compare_key]["primary_zip"]
            primary_address1 == columns_data[compare_key][check_same_address_columns[0]]
            and primary_zip == columns_data[compare_key][check_same_address_columns[1]]
        ):
            # found same address
            output_lines += [
                "Found someone with the same address as a selected person,"
                " so deleting him/her. Address: {} , {}".format(primary_address1, primary_zip)
            ]
            people_to_delete.append(compare_key)
    return people_to_delete, output_lines


# lucky person has been selected - delete person from DB
def delete_person(categories, people, pkey, columns_data, check_same_address, check_same_address_columns):
    output_lines = []
    # recalculate all category values that this person was in
    person = people[pkey]
    really_delete_person(categories, people, pkey, True)
    # check if there are other people at the same address - if so, remove them!
    if check_same_address:
        people_to_delete, output_lines = get_people_at_same_address(people, pkey, columns_data, check_same_address_columns)
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
    # check that the fieldnames are what we expect
    if cat_file.fieldnames != category_file_field_names:
        raise Exception(
            "ERROR reading in category file: expected first line to be {} ".format(category_file_field_names)
        )
    for row in cat_file:  # must convert min/max to ints
        # allow for some dirty data - at least strip white space from cat and name
        cat = row["category"].strip()
        cat_value = row["name"].strip()
        # must convert min/max to ints
        min = int(row["min"])
        max = int(row["max"])
        if cat in categories:
            min_max_people_cats[cat]["min"] += min
            min_max_people_cats[cat]["max"] += max
            categories[cat].update(
                {
                    cat_value: {
                        "min": min,
                        "max": max,
                        "selected": 0,
                        "remaining": 0,
                    }
                }
            )
        else:
            min_max_people_cats.update(
                {
                    cat: {
                        "min": min,
                        "max": max
                    }
                }
            )
            categories.update(
                {
                    cat: {
                        cat_value: {
                            "min": min,
                            "max": max,
                            "selected": 0,
                            "remaining": 0,
                        }
                    }
                }
            )
    return categories, min_max_people_cats


# read in people and calculate how many people in each category in database
def init_categories_people(people_file: typing.TextIO, categories, settings: Settings):
    people = {}
    columns_data = {}
    people_data = csv.DictReader(people_file)
    # check that id_column and all the categories and columns_to_keep are in the people data fields
    if settings.id_column not in people_data.fieldnames:
        raise Exception(
            "ERROR reading in people: no {} (unique id) column found in people data!".format(settings.id_column)
        )
    for cat_key in categories.keys():
        if cat_key not in people_data.fieldnames:
            raise Exception(
                "ERROR reading in people: no '{}' (category) column found in people data!".format(cat_key)
            )
    for column in settings.columns_to_keep:
        if column not in people_data.fieldnames:
            raise Exception(
                "ERROR reading in people: no '{}' column (to keep) found in people data!".format(column)
            )
    for column in settings.check_same_address_columns:
        if column not in people_data.fieldnames:
            raise Exception(
                "ERROR reading in people: no '{}' column (to check same address) found in people data!".format(column)
            )
    for row in people_data:
        pkey = row[settings.id_column]
        value = {}
        for cat_key, cats in categories.items():
            # check for input errors here - if it's not in the list of category values...
            # allow for some unclean data - at least strip empty space
            p_value = row[cat_key].strip()
            if p_value not in cats:
                raise Exception(
                    "ERROR reading in people (init_categories_people): Person (id = {}) has value '{}' not in category {}".format(pkey, p_value, cat_key)
                )
            value.update({cat_key: p_value})
            categories[cat_key][p_value]["remaining"] += 1
        people.update({pkey: value})
        # this is address, name etc that we need to keep for output file
        data_value = {}
        for col in settings.columns_to_keep:
            data_value[col] = row[col]
        columns_data.update({pkey: data_value})
    # check if any cat[max] is set to zero... if so delete everyone with that cat...
    # NOT DONE: could then check if anyone is left...
    msg = ["Number of people: {}.".format(len(people.keys()))]
    for cat_key, cats in categories.items():
        for cat, cat_item in cats.items():
            if cat_item["max"] == 0:  # we don't want any of these people
                msg += delete_all_in_cat(categories, people, cat_key, cat)
    return people, columns_data, msg


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


def _distribution_stats(people:  Dict[str, Dict[str, str]], allocations: List[FrozenSet[str]],
                        probabilities: List[float]) -> List[str]:
    output_lines = []

    assert len(allocations) == len(probabilities)
    num_non_zero = sum([1 for prob in probabilities if prob > 0])
    output_lines.append(f"Algorithm produced distribution over {len(allocations)} committees, out of which "
                        f"{num_non_zero} are chosen with positive probability.")

    individual_probabilities = {id: 0 for id in people}
    committees = {id: [] for id in people}
    for alloc, prob in zip(allocations, probabilities):
        if prob > 0:
            for id in alloc:
                individual_probabilities[id] += prob
                committees[id].append(alloc)

    table = ["<table border='1' cellpadding='5'><tr><th>Agent ID</th><th>Probability of selection</th><th>Included in #"
             "of committees</th></tr>"]

    for _, id in sorted((prob, id) for id, prob in individual_probabilities.items()):
        table.append(f"<tr><td>{id}</td><td>{individual_probabilities[id]:.4%}</td><td>{len(committees[id])}</td></tr>")
    table.append("</table>")
    output_lines.append("".join(table))

    return output_lines


def find_random_sample(categories: Dict[str, Dict[str, Dict[str, int]]], people: Dict[str, Dict[str, str]],
                       columns_data: Dict[str, Dict[str, str]], number_people_wanted: int, check_same_address: bool,
                       check_same_address_columns: List[str], selection_algorithm: str, fair_to_households: bool)\
                       -> Tuple[Dict[str, Dict[str, str]], List[str]]:
    """Main algorithm to try to find a random sample.

    Args:
        categories: categories["feature"]["value"] is a dictionary with keys "min", "max", "selected", "remaining".
        people: people["nationbuilder_id"] is dictionary mapping "feature" to "value" for a person.
        columns_data: columns_data["nationbuilder_id"] is dictionary mapping "contact_field" to "value" for a person.
        number_people_wanted:
        check_same_address:
        check_same_address_columns: list of contact fields of columns that have to be equal for being
            counted as residing at the same address
        selection_algorithm: one out of "legacy", "maximin", or "nash"
        fair_to_households: for maximin and nash algorithm, whether multiple members of the same household should
            only count as much as a single person from a single-person household
    Returns:
        (people_selected, output_lines)
        `people_selected` is a subdictionary of `people` with `number_people_wanted` many entries, guaranteed to satisfy
            the constraints on a feasible committee.
        `output_lines` is a list of debug strings.
    Side Effects:
        The "selected" and "remaining" fields in `categories` to be changed.
    """
    if selection_algorithm not in ["legacy", "maximin", "nash"]:
        raise ValueError(f"Unknown selection algorithm {repr(selection_algorithm)}.")
    elif selection_algorithm == "legacy":
        return find_random_sample_legacy(categories, people, columns_data, number_people_wanted, check_same_address, check_same_address_columns)

    if selection_algorithm == "maximin":
        raise NotImplementedError()
    elif selection_algorithm == "nash":
        allocations, probabilities, output_lines = find_distribution_nash(categories, people, columns_data,
                                                                          number_people_wanted, check_same_address,
                                                                          check_same_address_columns,
                                                                          fair_to_households)

    assert len(set(allocations)) == len(allocations)
    output_lines += _distribution_stats(people, allocations, probabilities)

    # choose a concrete committee from the distribution
    committee: FrozenSet[str] = np.random.choice(allocations, 1, p=probabilities)[0]
    people_selected = {id: people[id] for id in committee}

    # update categories for the algorithms other than legacy
    for id, person in people_selected.items():
        for feature in person:
            value = person[feature]
            categories[feature][value]["selected"] += 1
            categories[feature][value]["remaining"] -= 1
    return people_selected, output_lines


def find_random_sample_legacy(categories: Dict[str, Dict[str, Dict[str, int]]], people: Dict[str, Dict[str, str]],
                              columns_data: Dict[str, Dict[str, str]], number_people_wanted: int,
                              check_same_address: bool, check_same_address_columns: List[str]) \
                             -> Tuple[Dict[str, Dict[str, str]], List[str]]:
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
                    output_lines += delete_person(categories, people, pkey, columns_data, check_same_address, check_same_address_columns)
                    break
        if count < (number_people_wanted - 1) and len(people) == 0:
            raise SelectionError("Fail! We've run out of people...")
    return people_selected, output_lines


def _ilp_results_to_committee(variables: Dict[str, mip.entities.Var],
                              number_people_wanted: Optional[int] = None) -> FrozenSet[str]:
    try:
        res = frozenset(id for id in variables if variables[id].x > 0.5)
    except Exception as e:  # unfortunately, MIP sometimes throws generic Exceptions rather than a subclass.
        raise ValueError(f"It seems like some variables does not have a value. Original exception: {e}.")

    if number_people_wanted is not None:
        assert len(res) == number_people_wanted

    return res


def _same_address(columns_data1: Dict[str, str], columns_data2: Dict[str, str], check_same_address_columns: List[str]):
    return all(columns_data1[column] == columns_data2[column] for column in check_same_address_columns)


def _allocations_to_matrix_fair_to_individuals(allocations: List[FrozenSet[str]], entitled_agents: List[str]):
    columns = []
    for alloc in allocations:
        columns.append(np.array([int(id in alloc) for id in entitled_agents]))
    return np.column_stack(columns)


def _allocations_to_matrix_fair_to_households(allocations: List[FrozenSet[str]], entitled_households: List[str],
                                              address_groups: Dict[str, str]):
    columns = []
    for alloc in allocations:
        column_dict = {household: 0 for household in entitled_households}
        for id in alloc:
            column_dict[address_groups[id]] += 1
        column = [column_dict[household] for household in entitled_households]
        columns.append(np.array(column))
    return np.column_stack(columns)


def _print(message: str) -> str:
    print(message)
    return message


def find_distribution_nash(categories: Dict[str, Dict[str, Dict[str, int]]], people: Dict[str, Dict[str, str]],
                           columns_data: Dict[str, Dict[str, str]], number_people_wanted: int, check_same_address: bool,
                           check_same_address_columns: List[str], fair_to_households: bool) \
                          -> Tuple[List[FrozenSet[str]], List[float], List[str]]:
    """Find a distribution over feasible committees that maximizes the so-called Nash welfare, i.e., the product of
    selection probabilities over all persons (or over all households if `fair_to_households`).

    Arguments follow the pattern of `find_random_sample`.

    Returns:
        (allocations, probabilities, output_lines)
        `allocations` is a list of feasible committees, where each committee is represented by a frozen set of included
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
    # TODO:remove import
    from collections import Counter
    output_lines = []

    # `new_constraint_model` is an integer linear program (ILP) used for discovering new feasible committees.
    # We will use it many times, putting different weights on the inclusion of different agents to find many feasible
    # committees.
    # TODO: do not specify solver to able to use installed Gurobi where available, currently there for testing purposes
    new_constraint_model = mip.Model(sense=mip.MAXIMIZE, solver_name=mip.CBC)
    new_constraint_model.verbose = debug

    # for every person, we have a binary variable indicating whether they are in the committee
    constraint_agent_vars = {id: new_constraint_model.add_var(var_type=mip.BINARY) for id in people}

    # we have to select exactly `number_people_wanted` many persons
    new_constraint_model.add_constr(mip.xsum(constraint_agent_vars.values()) == number_people_wanted)

    # we have to respect quotas
    for feature in categories:
        for value in categories[feature]:
            number_feature_value_agents = mip.xsum(constraint_agent_vars[id] for id, person in people.items()
                                                   if person[feature] == value)
            new_constraint_model.add_constr(number_feature_value_agents >= categories[feature][value]["min"])
            new_constraint_model.add_constr(number_feature_value_agents <= categories[feature][value]["max"])

    # we might not be able to select multiple persons from the same household
    if check_same_address:
        ids = list(people.keys())
        address_groups = {id: None for id in people} # for each agent, the id of the earliest person with same address

        for i, id1 in enumerate(ids):
            if address_groups[id1] is not None:
                continue
            address_groups[id1] = id1
            house_vars = [constraint_agent_vars[id1]]
            for id2 in ids[i + 1:]:
                if address_groups[id2] is None and _same_address(columns_data[id1], columns_data[id2], check_same_address_columns):
                    address_groups[id2] = id1
                    house_vars.append(constraint_agent_vars[id2])
            if len(house_vars) >= 2:
                new_constraint_model.add_constr(mip.xsum(house_vars) <= 1)

    # Optimize once without any constraints to check if no feasible committees exist at all.
    status = new_constraint_model.optimize()
    if status != mip.OptimizationStatus.OPTIMAL:
        raise ValueError(f"No feasible committees found, solver returns code {status} (see https://docs.python-mip.com/"
                         "en/latest/classes.html#optimizationstatus). Excluding a solver failure, the quotas are "
                         "unsatisfiable.")

    # Start by finding committees including every agent, and learn which agents cannot possibly be included.
    allocations: List[FrozenSet[str]] = []  # set of feasible committees, add more over time
    agent_covered = {id: False for id in people}
    for id in people:
        if not agent_covered[id]:
            # try to find an objective in which agent `id` is selected
            new_constraint_model.objective = constraint_agent_vars[id]
            new_constraint_model.optimize()
            new_set: FrozenSet[str] = _ilp_results_to_committee(constraint_agent_vars, number_people_wanted)
            if id not in new_set:
                output_lines.append(
                    _print(f"Agent {id} is not contained in any feasible committee. Maybe relax quotas?"))
            else:
                assert new_set not in allocations
                allocations.append(new_set)
                for id2 in new_set:
                    agent_covered[id2] = True
    assert len(allocations) >= 1
    if all(agent_covered.values()):
        output_lines.append(_print("All agents are contained in some feasible committee."))

    if fair_to_households:
        entitled_households = list(set(address_groups[id] for id in agent_covered if agent_covered[id]))
        num_entitlements = len(entitled_households)
        contributes_to_index = {}
        for id in people:
            try:
                contributes_to_index[id] = entitled_households.index(address_groups[id])
            except ValueError:
                pass
    else:
        entitled_agents = [id for id in agent_covered if agent_covered[id]]
        num_entitlements = len(entitled_agents)
        contributes_to_index = {}
        for id in people:
            try:
                contributes_to_index[id] = entitled_agents.index(id)
            except ValueError:
                pass

    # Now, the algorithm proceeds iteratively. First, it finds probabilities for the committees already present in
    # `allocations` that maximize the sum of logarithms. Then, reusing the old ILP, it finds the feasible committee
    # (possibly outside of `allocations`) such that the partial derivative of the sum of logarithms with respect to the
    # probability of outputting this committee is maximal. If this partial derivative is less than the maximal partial
    # derivative of any committee already in `allocations`, the Karush-Kuhn-Tucker conditions (which are sufficient in
    # this case) imply that the distribution is optimal even with all other committees receiving probability 0.
    start_lambdas = [1 / len(allocations) for _ in allocations]
    while True:
        lambdas = cp.Variable(len(allocations))  # probability of outputting a specific committee
        lambdas.value = start_lambdas
        # A is a binary matrix, whose (i,j)th entry indicates whether agent `feasible_agents[i]`
        if fair_to_households:
            A = _allocations_to_matrix_fair_to_households(allocations, entitled_households, address_groups)
        else:
            A = _allocations_to_matrix_fair_to_individuals(allocations, entitled_agents)
        assert A.shape == (num_entitlements, len(allocations))

        objective = cp.Maximize(cp.sum(cp.log(A * lambdas)))
        constraints = [0 <= lambdas, sum(lambdas) == 1]
        problem = cp.Problem(objective, constraints)
        # TODO: test relative performance of both solvers, see whether warm_start helps.
        try:
            nash_welfare = problem.solve(solver=cp.ECOS, warm_start=True)
        except cp.SolverError:
            # Sometimes, the ECOS solver in cvxpy crashes (numerical instabilities?). In this case, try another solver.
            output_lines.append(_print("Had to switch to SCS solver."))
            nash_welfare = problem.solve(solver=cp.SCS, warm_start=True)
        scaled_welfare = nash_welfare - num_entitlements * log(number_people_wanted / num_entitlements)
        output_lines.append(_print(f"Scaled Nash welfare is now: {scaled_welfare}."))

        assert lambdas.value.shape == (len(allocations),)
        entitled_utilities = A.dot(lambdas.value)
        assert entitled_utilities.shape == (num_entitlements,)
        assert((entitled_utilities > EPS2).all())
        entitled_reciprocals = 1 / entitled_utilities
        assert entitled_reciprocals.shape == (num_entitlements,)
        differentials = entitled_reciprocals.dot(A)
        assert differentials.shape == (len(allocations),)
        # TODO: delete
        #diffs2 = [diff for diff, l in zip(differentials, lambdas) if l.value > 0.0002]
        #print("diffs:", Counter(differentials.round(2)))

        obj = []
        for id in people:
            if id in contributes_to_index:
                obj.append(entitled_reciprocals[contributes_to_index[id]] * constraint_agent_vars[id])
        new_constraint_model.objective = mip.xsum(obj)
        new_constraint_model.optimize()

        new_set = _ilp_results_to_committee(constraint_agent_vars, number_people_wanted)
        value = sum(entitled_reciprocals[contributes_to_index[id]] for id in new_set if id in contributes_to_index)
        if value <= differentials.max() + EPS:
            probabilities = np.array(lambdas.value).clip(0, 1)
            probabilities = list(probabilities / sum(probabilities))
            # TODO: filter 0-probability allocations?
            return allocations, probabilities, output_lines
        else:
            print(value, differentials.max(), value - differentials.max())
            assert new_set not in allocations
            allocations.append(new_set)
            start_lambdas = np.array(lambdas.value).resize(len(allocations))


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


def run_stratification(categories, people, columns_data, number_people_wanted, min_max_people, settings: Settings):
    # First check if numbers in cat file and to select make sense
    for mkey, mvalue in min_max_people.items():
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
    output_lines = ["<b>Initial: (selected = 0, remaining = {})</b>".format(len(people.keys()))]
    while not success and tries < settings.max_attempts:
        people_selected = {}
        new_output_lines = []
        people_working = copy.deepcopy(people)
        categories_working = copy.deepcopy(categories)
        if tries == 0:
            output_lines += print_category_selected(categories_working, number_people_wanted)
        output_lines.append("<b>Trial number: {}</b>".format(tries))
        try:
            people_selected, new_output_lines = find_random_sample(categories_working, people_working, columns_data, number_people_wanted,
                                                                   settings.check_same_address, settings.check_same_address_columns,
                                                                   settings.selection_algorithm, settings.fair_to_households)
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
# BUT, we should not include in this people from the same address as someone who has been selected!
def write_selected_people_to_file(people, people_selected, categories, columns_data, selected_file, remaining_file, settings: Settings):
    people_working = copy.deepcopy(people)
    people_selected_writer = csv.writer(
        selected_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
    )
    people_selected_writer.writerow(
        [settings.id_column] + settings.columns_to_keep + list(categories.keys())
    )
    output_lines = []  # do we want to output same address info?
    num_same_address_deleted = 0
    for pkey, person in people_selected.items():
        row = [pkey]
        for col in settings.columns_to_keep:
            row.append(columns_data[pkey][col])
        row += person.values()
        people_selected_writer.writerow(row)
        # if check address then delete all those at this address (will delete the one we want as well)
        if settings.check_same_address:
            people_to_delete, new_output_lines = get_people_at_same_address(people_working, pkey, columns_data, settings.check_same_address_columns)
            output_lines += new_output_lines
            num_same_address_deleted += len(new_output_lines) - 1  # don't include original
            # then delete this/these people at the same address from the reserve/remaining pool
            for del_person_key in people_to_delete:
                del people_working[del_person_key]
        else:
            del people_working[pkey]

    people_remaining_writer = csv.writer(
        remaining_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
    )
    people_remaining_writer.writerow(
        [settings.id_column] + settings.columns_to_keep + list(categories.keys())
    )
    for pkey, person in people_working.items():
        row = [pkey]
        for col in settings.columns_to_keep:
            row.append(columns_data[pkey][col])
        row += person.values()
        people_remaining_writer.writerow(row)
    output_lines = ["Deleted {} people from remaining file who had the same address as selected people.".format(num_same_address_deleted)]
    return output_lines
