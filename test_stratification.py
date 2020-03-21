from copy import deepcopy
from dataclasses import dataclass
from itertools import combinations
from unittest import TestCase

from stratification import *


@dataclass
class Example:
    categories: Dict[str, Dict[str, Dict[str, int]]]
    people: Dict[str, Dict[str, str]]
    columns_data: Dict[str, Dict[str, str]]
    number_people_wanted: int


example1 = Example({"age":
                        {"child": {"min": 1, "max": 2},
                         "adult": {"min": 1, "max": 2}},
                    "franchise":
                        {"simpsons": {"min": 1, "max": 2},
                         "ducktales": {"min": 1, "max": 2}}},
                   {"lisa": {"age": "child", "franchise": "simpsons"},
                    "marge": {"age": "adult", "franchise": "simpsons"},
                    "louie": {"age": "child", "franchise": "ducktales"},
                    "dewey": {"age": "child", "franchise": "ducktales"},
                    "scrooge": {"age": "adult", "franchise": "ducktales"}},
                   {"lisa": {"home": "1"},
                    "marge": {"home": "3"},
                    "louie": {"home": "2"},
                    "dewey": {"home": "2"},
                    "scrooge": {"home": "1"}},
                   2)

example2 = deepcopy(example1)
example2.columns_data = {"lisa": {"home": "1"},
                         "marge": {"home": "3"},
                         "louie": {"home": "1"},
                         "dewey": {"home": "2"},
                         "scrooge": {"home": "1"}}

# In this example, every committee must include agent "a" because that is the only way to get a v1 agent for all three
# features with only two agents on the committee.
example3 = Example({"f1":
                        {"v1": {"min": 1, "max": 2},
                         "v2": {"min": 0, "max": 2}},
                    "f2":
                        {"v1": {"min": 1, "max": 2},
                         "v2": {"min": 0, "max": 2}},
                    "f3":
                        {"v1": {"min": 1, "max": 2},
                         "v2": {"min": 0, "max": 2}}},
                   {"a": {"f1": "v1", "f2": "v1", "f3": "v1"},
                    "b": {"f1": "v1", "f2": "v2", "f3": "v2"},
                    "c": {"f1": "v2", "f2": "v1", "f3": "v2"},
                    "d": {"f1": "v2", "f2": "v2", "f3": "v1"}},
                   {"a": {"home": "1"},
                    "b": {"home": "2"},
                    "c": {"home": "3"},
                    "d": {"home": "3"}},
                   2)

# Because we need _exactly_ one v1 agent from every agent, there are no feasible committees. Any committee without "a"
# does not have any v1 agent for one of the three features; if "a" is combined with any other agent, one feature will
# have to v1 agents."""
example4 = deepcopy(example3)
example4.categories = {"f1":
                           {"v1": {"min": 1, "max": 1},
                            "v2": {"min": 0, "max": 2}},
                       "f2":
                           {"v1": {"min": 1, "max": 1},
                            "v2": {"min": 0, "max": 2}},
                       "f3":
                           {"v1": {"min": 1, "max": 1},
                            "v2": {"min": 0, "max": 2}}}


def _calculate_marginals(people, committees, probabilities):
    marginals = {id: 0 for id in people}
    for committee, prob in zip(committees, probabilities):
        for id in committee:
            marginals[id] += prob
    return marginals


class Test(TestCase):
    def _probabilities_well_formed(self, probabilities):
        self.assertGreaterEqual(len(probabilities), 1)
        for prob in probabilities:
            self.assertGreaterEqual(prob, 0)
            self.assertLessEqual(prob, 1)
        prob_sum = sum(probabilities)
        self.assertAlmostEqual(prob_sum, 1)

    def _allocation_feasible(self, allocation, categories, people, columns_data, number_people_wanted,
                             check_same_address, check_same_address_columns):
        self.assertEqual(len(allocation), len(set(allocation)))
        self.assertEqual(len(allocation), number_people_wanted)
        for id in allocation:
            self.assertIn(id, people)
        for feature in categories:
            for value in categories[feature]:
                num_value = sum(1 for id in allocation if people[id][feature] == value)
                self.assertGreaterEqual(num_value, categories[feature][value]["min"])
                self.assertLessEqual(num_value, categories[feature][value]["max"])
        if check_same_address:
            for id1, id2 in combinations(allocation, r=2):
                self.assertNotEqual([columns_data[id1][col] for col in check_same_address_columns],
                                    [columns_data[id2][col] for col in check_same_address_columns])

    def test_find_distribution_maximin_no_adress_fair_to_people_1(self):
        categories = example1.categories
        people = example1.people
        columns_data = example1.columns_data
        number_people_wanted = example1.number_people_wanted
        check_same_address = False
        check_same_address_columns = []
        fair_to_households = False
        committees, probabilities, _ = find_distribution_maximin(categories, people, columns_data, number_people_wanted,
                                                                 check_same_address, check_same_address_columns,
                                                                 fair_to_households)
        self._probabilities_well_formed(probabilities)
        for committee in committees:
            self._allocation_feasible(committee, categories, people, columns_data, number_people_wanted,
                                      check_same_address,
                                      check_same_address_columns)

        # maximin is 1/3, can be achieved uniquely by
        # 1/3: {louie, marge}, 1/3: {dewey, marge}, 1/3: {scrooge, lisa}
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertAlmostEqual(marginals["lisa"], 1 / 3)
        self.assertAlmostEqual(marginals["scrooge"], 1 / 3)
        self.assertAlmostEqual(marginals["louie"], 1 / 3)
        self.assertAlmostEqual(marginals["dewey"], 1 / 3)
        self.assertAlmostEqual(marginals["marge"], 2 / 3)

    def test_find_distribution_maximin_adress_fair_to_people(self):
        categories = example1.categories
        people = example1.people
        columns_data = example1.columns_data
        number_people_wanted = example1.number_people_wanted
        check_same_address = True
        check_same_address_columns = ["home"]
        fair_to_households = False
        committees, probabilities, _ = find_distribution_maximin(categories, people, columns_data, number_people_wanted,
                                                                 check_same_address, check_same_address_columns,
                                                                 fair_to_households)
        self._probabilities_well_formed(probabilities)
        for committee in committees:
            self._allocation_feasible(committee, categories, people, columns_data, number_people_wanted,
                                      check_same_address,
                                      check_same_address_columns)

        # Scrooge and Lisa can no longer be included. E.g. if Scrooge is included, we need a simpsons child for the
        # second position. Only Lisa qualifies, but lives in the same household. Unique maximin among everyone else is:
        # 1/2: {louie, marge}, 1/2: {dewey, marge}
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertAlmostEqual(marginals["lisa"], 0)
        self.assertAlmostEqual(marginals["scrooge"], 0)
        self.assertAlmostEqual(marginals["louie"], 1 / 2)
        self.assertAlmostEqual(marginals["dewey"], 1 / 2)
        self.assertAlmostEqual(marginals["marge"], 1)

    def test_find_distribution_maximin_no_adress_fair_to_households(self):
        categories = example2.categories
        people = example2.people
        columns_data = example2.columns_data
        number_people_wanted = example2.number_people_wanted
        check_same_address = False
        check_same_address_columns = ["home"]
        fair_to_households = True
        committees, probabilities, _ = find_distribution_maximin(categories, people, columns_data, number_people_wanted,
                                                                 check_same_address, check_same_address_columns,
                                                                 fair_to_households)
        self._probabilities_well_formed(probabilities)
        for committee in committees:
            self._allocation_feasible(committee, categories, people, columns_data, number_people_wanted,
                                      check_same_address,
                                      check_same_address_columns)

        # maximin is 2/3 (for households), can be achieved uniquely by
        # 2/3: {dewey, marge}, 1/3: {scrooge, lisa}
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertAlmostEqual(marginals["lisa"], 1 / 3)
        self.assertAlmostEqual(marginals["scrooge"], 1 / 3)
        self.assertAlmostEqual(marginals["louie"], 0)
        self.assertAlmostEqual(marginals["dewey"], 2 / 3)
        self.assertAlmostEqual(marginals["marge"], 2 / 3)

    def test_find_distribution_maximin_adress_fair_to_households_1(self):
        categories = example2.categories
        people = example2.people
        columns_data = example2.columns_data
        number_people_wanted = example2.number_people_wanted
        check_same_address = True
        check_same_address_columns = ["home"]
        fair_to_households = True
        committees, probabilities, _ = find_distribution_maximin(categories, people, columns_data, number_people_wanted,
                                                                 check_same_address, check_same_address_columns,
                                                                 fair_to_households)
        self._probabilities_well_formed(probabilities)
        for committee in committees:
            self._allocation_feasible(committee, categories, people, columns_data, number_people_wanted,
                                      check_same_address,
                                      check_same_address_columns)

        # Scrooge and Lisa can no longer be included. E.g. if Scrooge is included, we need a simpsons child for the
        # second position. Only Lisa qualifies, but lives in the same household. Unique maximin among households is 1/2:
        # 1/2: {louie, marge}, 1/2: {dewey, marge}
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertAlmostEqual(marginals["lisa"], 0)
        self.assertAlmostEqual(marginals["scrooge"], 0)
        self.assertAlmostEqual(marginals["louie"], 1 / 2)
        self.assertAlmostEqual(marginals["dewey"], 1 / 2)
        self.assertAlmostEqual(marginals["marge"], 1)

    def test_find_distribution_maximin_adress_fair_to_people_2(self):
        categories = example3.categories
        people = example3.people
        columns_data = example3.columns_data
        number_people_wanted = example3.number_people_wanted
        check_same_address = False
        check_same_address_columns = []
        fair_to_households = False
        committees, probabilities, _ = find_distribution_maximin(categories, people, columns_data, number_people_wanted,
                                                                 check_same_address, check_same_address_columns,
                                                                 fair_to_households)
        self._probabilities_well_formed(probabilities)
        for committee in committees:
            self._allocation_feasible(committee, categories, people, columns_data, number_people_wanted,
                                      check_same_address,
                                      check_same_address_columns)

        # maximin is 1/3, can be achieved uniquely by
        # 1/3: {a, b}, 1/3: {a, c}, 1/3: {a, d}
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertAlmostEqual(marginals["a"], 1)
        self.assertAlmostEqual(marginals["b"], 1 / 3)
        self.assertAlmostEqual(marginals["c"], 1 / 3)
        self.assertAlmostEqual(marginals["d"], 1 / 3)

    def test_find_distribution_maximin_no_adress_fair_to_people_2(self):
        categories = example3.categories
        people = example3.people
        columns_data = example3.columns_data
        number_people_wanted = example3.number_people_wanted
        check_same_address = False
        check_same_address_columns = ["home"]
        fair_to_households = True
        committees, probabilities, _ = find_distribution_maximin(categories, people, columns_data, number_people_wanted,
                                                                 check_same_address, check_same_address_columns,
                                                                 fair_to_households)
        self._probabilities_well_formed(probabilities)
        for committee in committees:
            self._allocation_feasible(committee, categories, people, columns_data, number_people_wanted,
                                      check_same_address,
                                      check_same_address_columns)

        # maximin is 1/3, can be achieved by
        # 1/2: {a, b}, α: {a, c}, (1/2 - α): {a, d} for any α
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertAlmostEqual(marginals["a"], 1)
        self.assertAlmostEqual(marginals["b"], 1 / 2)
        self.assertAlmostEqual(marginals["c"] + marginals["d"], 1 / 2)

    def test_find_distribution_maximin_no_adress_fair_to_people_2(self):
        categories = example3.categories
        people = example3.people
        columns_data = example3.columns_data
        number_people_wanted = example3.number_people_wanted
        check_same_address = False
        check_same_address_columns = []  # SIC: all in same household. That's okay because we allow multiple members.
        fair_to_households = True
        committees, probabilities, _ = find_distribution_maximin(categories, people, columns_data, number_people_wanted,
                                                                 check_same_address, check_same_address_columns,
                                                                 fair_to_households)
        self._probabilities_well_formed(probabilities)
        for committee in committees:
            self._allocation_feasible(committee, categories, people, columns_data, number_people_wanted,
                                      check_same_address,
                                      check_same_address_columns)

    def test_find_distribution_maximin_no_adress_fair_to_people_3(self):
        categories = example4.categories
        people = example4.people
        columns_data = example4.columns_data
        number_people_wanted = example4.number_people_wanted
        check_same_address = False
        check_same_address_columns = ["home"]
        fair_to_households = False

        # There are no feasible committees at all.
        with self.assertRaises(ValueError):
            find_distribution_maximin(categories, people, columns_data, number_people_wanted, check_same_address,
                                      check_same_address_columns, fair_to_households)