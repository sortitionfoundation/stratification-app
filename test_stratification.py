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

# Categories: gender (female/male) and political leaning (liberal/conservative)
# Quotas: must include exactly 4 males, 1 female, 4 liberals, and 1 conservative.
# Pool: 4 liberal men, 1 liberal female, 1 conservative male, 1 conservative female.
# k = 5
example5 = Example({"gender":
                        {"female": {"min": 1, "max": 1},
                         "male": {"min": 4, "max": 4}},
                    "political":
                        {"liberal": {"min": 4, "max": 4},
                         "conservative": {"min": 1, "max": 1}}
                    },
                   {"adam": {"gender": "male", "political": "liberal"},
                    "brian": {"gender": "male", "political": "liberal"},
                    "cameron": {"gender": "male", "political": "liberal"},
                    "dave": {"gender": "male", "political": "liberal"},
                    "elinor": {"gender": "female", "political": "liberal"},
                    "frank": {"gender": "male", "political": "conservative"},
                    "grace": {"gender": "female", "political": "conservative"}},
                   {"adam": {},
                    "brian": {},
                    "cameron": {},
                    "dave": {},
                    "elinor": {},
                    "frank": {},
                    "grace": {}},
                   5)

# In this example, agent "p61" cannot be chosen for the committee, but in a somewhat subtle way. Consider just groups
# A, B, and C for now (D, E, and F are symmetric). The lower quotas on the v1's need at least 23 agents on A, B, and C;
# e.g. it could place 8 on A, 8 on B, and 7 on C. The same is true for D, E, and F; so none of the 46 seats is free for
# the extra person. This is subtle because the situation would be very different if we could choose fractions of a
# person on our committee. Then, we could choose 7.5 people from A through F each and even choose the extra person each
# time, or choose every person with equal probability.
example6_categories = {"f1": {"v1": {"min": 15, "max": 46},  # at least 15 people from A & B together
                              "v2": {"min": 15, "max": 46},  # at least 15 people from D & E together
                              "v3": {"min": 0, "max": 46}},
                       "f2": {"v1": {"min": 15, "max": 46},  # at least 15 people from A & C together
                              "v2": {"min": 15, "max": 46},  # at least 15 people from D & F together
                              "v3": {"min": 0, "max": 46}},
                       "f3": {"v1": {"min": 15, "max": 46},  # at least 15 people from B & C together
                              "v2": {"min": 15, "max": 46},  # at least 15 people from E & F together
                              "v3": {"min": 0, "max": 46}}}
example6_people = {}
for i in range(1, 11):
    example6_people['p' + str(i)]      = {"f1": "v1", "f2": "v1", "f3": "v3"}  # 10 people of kind A
    example6_people['p' + str(i + 10)] = {"f1": "v1", "f2": "v3", "f3": "v1"}  # 10 people of kind B
    example6_people['p' + str(i + 20)] = {"f1": "v3", "f2": "v1", "f3": "v1"}  # 10 people of kind C
    example6_people['p' + str(i + 30)] = {"f1": "v2", "f2": "v2", "f3": "v3"}  # 10 people of kind D
    example6_people['p' + str(i + 40)] = {"f1": "v2", "f2": "v3", "f3": "v2"}  # 10 people of kind E
    example6_people['p' + str(i + 50)] = {"f1": "v3", "f2": "v2", "f3": "v2"}  # 10 people of kind F
example6_people['p61']                 = {"f1": "v3", "f2": "v3", "f3": "v3"}  # 1 extra person
example6_columns_data = {id: {} for id in example6_people}
example6 = Example(example6_categories, example6_people, example6_columns_data, 46)


def _calculate_marginals(people, committees, probabilities):
    marginals = {id: 0 for id in people}
    for committee, prob in zip(committees, probabilities):
        for id in committee:
            marginals[id] += prob
    return marginals


class FindDistributionTests(TestCase):
    PRECISION = 5

    def _probabilities_well_formed(self, probabilities):
        self.assertGreaterEqual(len(probabilities), 1)
        for prob in probabilities:
            self.assertGreaterEqual(prob, 0)
            self.assertLessEqual(prob, 1)
        prob_sum = sum(probabilities)
        self.assertAlmostEqual(prob_sum, 1, self.PRECISION)

    def _allocation_feasible(self, committee, categories, people, columns_data, number_people_wanted,
                             check_same_address, check_same_address_columns):
        self.assertEqual(len(committee), len(set(committee)))
        self.assertEqual(len(committee), number_people_wanted)
        for id in committee:
            self.assertIn(id, people)
        for feature in categories:
            for value in categories[feature]:
                num_value = sum(1 for id in committee if people[id][feature] == value)
                self.assertGreaterEqual(num_value, categories[feature][value]["min"])
                self.assertLessEqual(num_value, categories[feature][value]["max"])
        if check_same_address:
            for id1, id2 in combinations(committee, r=2):
                self.assertNotEqual([columns_data[id1][col] for col in check_same_address_columns],
                                    [columns_data[id2][col] for col in check_same_address_columns])

    def _distribution_okay(self, committees, probabilities, categories, people, columns_data, number_people_wanted,
                           check_same_address, check_same_address_columns):
        self._probabilities_well_formed(probabilities)
        for committee in committees:
            self._allocation_feasible(committee, categories, people, columns_data, number_people_wanted,
                                      check_same_address,
                                      check_same_address_columns)


class FindDistributionMaximinTests(FindDistributionTests):
    def test_no_address_fair_to_people_1(self):
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
        self._distribution_okay(committees, probabilities, categories, people, columns_data, number_people_wanted,
                                check_same_address, check_same_address_columns)

        # maximin is 1/3, can be achieved uniquely by
        # 1/3: {louie, marge}, 1/3: {dewey, marge}, 1/3: {scrooge, lisa}
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertAlmostEqual(marginals["lisa"], 1 / 3, self.PRECISION)
        self.assertAlmostEqual(marginals["scrooge"], 1 / 3, self.PRECISION)
        self.assertAlmostEqual(marginals["louie"], 1 / 3, self.PRECISION)
        self.assertAlmostEqual(marginals["dewey"], 1 / 3, self.PRECISION)
        self.assertAlmostEqual(marginals["marge"], 2 / 3, self.PRECISION)

    def test_address_fair_to_people_1(self):
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
        self._distribution_okay(committees, probabilities, categories, people, columns_data, number_people_wanted,
                                check_same_address, check_same_address_columns)

        # Scrooge and Lisa can no longer be included. E.g. if Scrooge is included, we need a simpsons child for the
        # second position. Only Lisa qualifies, but lives in the same household. Unique maximin among everyone else is:
        # 1/2: {louie, marge}, 1/2: {dewey, marge}
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertAlmostEqual(marginals["lisa"], 0, self.PRECISION)
        self.assertAlmostEqual(marginals["scrooge"], 0, self.PRECISION)
        self.assertAlmostEqual(marginals["louie"], 1 / 2, self.PRECISION)
        self.assertAlmostEqual(marginals["dewey"], 1 / 2, self.PRECISION)
        self.assertAlmostEqual(marginals["marge"], 1, self.PRECISION)

    def test_no_address_fair_to_households_1(self):
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
        self._distribution_okay(committees, probabilities, categories, people, columns_data, number_people_wanted,
                                check_same_address, check_same_address_columns)

        # maximin is 2/3 (for households), can be achieved uniquely by
        # 2/3: {dewey, marge}, 1/3: {scrooge, lisa}
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertAlmostEqual(marginals["lisa"], 1 / 3, self.PRECISION)
        self.assertAlmostEqual(marginals["scrooge"], 1 / 3, self.PRECISION)
        self.assertAlmostEqual(marginals["louie"], 0, self.PRECISION)
        self.assertAlmostEqual(marginals["dewey"], 2 / 3, self.PRECISION)
        self.assertAlmostEqual(marginals["marge"], 2 / 3, self.PRECISION)

    def test_address_fair_to_households_1(self):
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
        self._distribution_okay(committees, probabilities, categories, people, columns_data, number_people_wanted,
                                check_same_address, check_same_address_columns)

        # Scrooge and Lisa can no longer be included. E.g. if Scrooge is included, we need a simpsons child for the
        # second position. Only Lisa qualifies, but lives in the same household. Unique maximin among households is 1/2:
        # 1/2: {louie, marge}, 1/2: {dewey, marge}
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertEqual(marginals["lisa"], 0)
        self.assertAlmostEqual(marginals["scrooge"], 0, self.PRECISION)
        self.assertAlmostEqual(marginals["louie"], 1 / 2, self.PRECISION)
        self.assertAlmostEqual(marginals["dewey"], 1 / 2, self.PRECISION)
        self.assertAlmostEqual(marginals["marge"], 1, self.PRECISION)

    def test_no_address_fair_to_people_2(self):
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
        self._distribution_okay(committees, probabilities, categories, people, columns_data, number_people_wanted,
                                check_same_address, check_same_address_columns)

        # maximin is 1/3, can be achieved uniquely by
        # 1/3: {a, b}, 1/3: {a, c}, 1/3: {a, d}
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertAlmostEqual(marginals["a"], 1, self.PRECISION)
        self.assertAlmostEqual(marginals["b"], 1 / 3, self.PRECISION)
        self.assertAlmostEqual(marginals["c"], 1 / 3, self.PRECISION)
        self.assertAlmostEqual(marginals["d"], 1 / 3, self.PRECISION)

    def test_no_address_fair_to_households_2(self):
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
        self._distribution_okay(committees, probabilities, categories, people, columns_data, number_people_wanted,
                                check_same_address, check_same_address_columns)

        # maximin for households is 1/2, can be achieved by
        # 1/2: {a, b}, α: {a, c}, (1/2 - α): {a, d} for any α
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertAlmostEqual(marginals["a"], 1, self.PRECISION)
        self.assertAlmostEqual(marginals["b"], 1 / 2, self.PRECISION)
        self.assertAlmostEqual(marginals["c"] + marginals["d"], 1 / 2, self.PRECISION)

    def test_no_address_fair_to_households_3(self):
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
        self._distribution_okay(committees, probabilities, categories, people, columns_data, number_people_wanted,
                                check_same_address, check_same_address_columns)

    def test_no_address_fair_to_people_3(self):
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

    def test_no_address_fair_to_people_4(self):
        categories = example5.categories
        people = example5.people
        columns_data = example5.columns_data
        number_people_wanted = example5.number_people_wanted
        check_same_address = False
        check_same_address_columns = []
        fair_to_households = False
        committees, probabilities, _ = find_distribution_maximin(categories, people, columns_data,
                                                                 number_people_wanted,
                                                                 check_same_address, check_same_address_columns,
                                                                 fair_to_households)
        self._distribution_okay(committees, probabilities, categories, people, columns_data, number_people_wanted,
                                check_same_address, check_same_address_columns)

        # maximin is 1/2 (for individuals)
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertGreaterEqual(marginals["adam"], 1 / 2 - 1e-5)
        self.assertGreaterEqual(marginals["brian"], 1 / 2 - 1e-05)
        self.assertGreaterEqual(marginals["cameron"], 1 / 2 - 1e-05)
        self.assertGreaterEqual(marginals["dave"], 1 / 2 - 1e-05)
        self.assertGreaterEqual(marginals["frank"], 1 / 2 - 1e-05)
        self.assertAlmostEqual(marginals["elinor"], 1 / 2, self.PRECISION)
        self.assertAlmostEqual(marginals["grace"], 1 / 2, self.PRECISION)

    def test_no_address_fair_to_people_5(self):
        categories = example6.categories
        people = example6.people
        columns_data = example6.columns_data
        number_people_wanted = example6.number_people_wanted
        check_same_address = False
        check_same_address_columns = []
        fair_to_households = False
        committees, probabilities, _ = find_distribution_maximin(categories, people, columns_data, number_people_wanted,
                                                                 check_same_address, check_same_address_columns,
                                                                 fair_to_households)
        self._distribution_okay(committees, probabilities, categories, people, columns_data, number_people_wanted,
                                check_same_address, check_same_address_columns)

        # The full maximin is 0 because p61 cannot be selected. But our algorithm should aim for the maximin among the
        # remaining agents, which means choosing everyone else with probability 46/60.
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertEqual(marginals["p61"], 0)
        for i in range(1, 61):
            self.assertAlmostEqual(marginals["p" + str(i)], 46 / 60, self.PRECISION)


class FindDistributionNashTests(FindDistributionTests):
    PRECISION = 3

    def test_no_address_fair_to_people_3(self):
        categories = example4.categories
        people = example4.people
        columns_data = example4.columns_data
        number_people_wanted = example4.number_people_wanted
        check_same_address = False
        check_same_address_columns = ["home"]
        fair_to_households = False

        # There are no feasible committees at all.
        with self.assertRaises(ValueError):
            find_distribution_nash(categories, people, columns_data, number_people_wanted, check_same_address,
                                   check_same_address_columns, fair_to_households)

    def test_no_address_fair_to_people_4(self):
        categories = example5.categories
        people = example5.people
        columns_data = example5.columns_data
        number_people_wanted = example5.number_people_wanted
        check_same_address = False
        check_same_address_columns = []
        fair_to_households = False
        committees, probabilities, _ = find_distribution_nash(categories, people, columns_data,
                                                              number_people_wanted,
                                                              check_same_address, check_same_address_columns,
                                                              fair_to_households)
        self._probabilities_well_formed(probabilities)
        for committee in committees:
            self._allocation_feasible(committee, categories, people, columns_data, number_people_wanted,
                                      check_same_address,
                                      check_same_address_columns)

        # hand-calculated unique nash optimum
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertAlmostEqual(marginals["adam"], 6 / 7, self.PRECISION)
        self.assertAlmostEqual(marginals["brian"], 6 / 7, self.PRECISION)
        self.assertAlmostEqual(marginals["cameron"], 6 / 7, self.PRECISION)
        self.assertAlmostEqual(marginals["dave"], 6 / 7, self.PRECISION)
        self.assertAlmostEqual(marginals["frank"], 4 / 7, self.PRECISION)
        self.assertAlmostEqual(marginals["elinor"], 4 / 7, self.PRECISION)
        self.assertAlmostEqual(marginals["grace"], 3 / 7, self.PRECISION)

    def  test_no_address_fair_to_people_5(self):
        categories = example6.categories
        people = example6.people
        columns_data = example6.columns_data
        number_people_wanted = example6.number_people_wanted
        check_same_address = False
        check_same_address_columns = []
        fair_to_households = False
        committees, probabilities, _ = find_distribution_nash(categories, people, columns_data, number_people_wanted,
                                                              check_same_address, check_same_address_columns,
                                                              fair_to_households)
        self._distribution_okay(committees, probabilities, categories, people, columns_data, number_people_wanted,
                                check_same_address, check_same_address_columns)

        # The full maximin is -∞ because p61 cannot be selected. But our algorithm should maximize the Nash welfare of
        # the remaining agents, which means choosing everyone else with probability 46/60.
        marginals = _calculate_marginals(people, committees, probabilities)
        self.assertEqual(marginals["p61"], 0)
        for i in range(1, 61):
            self.assertAlmostEqual(marginals["p" + str(i)], 46 / 60, self.PRECISION - 1)
