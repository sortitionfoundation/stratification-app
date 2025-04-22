from pathlib import Path

import pytest

from stratification import (
	PeopleAndCatsCSV,
	Settings,
)

# legacy is broken, so exclude that for now
ALGORITHMS = ("legacy", "maximin", "leximin", "nash")

categories_content = Path("fixtures/categories.csv").read_text("utf8")
candidates_content = Path("fixtures/candidates.csv").read_text("utf8")
candidates_lines = [l.strip() for l in candidates_content.split("\n") if l.strip()]

"""
The header line of candidates.csv is:
nationbuilder_id,first_name,last_name,email,mobile_number,primary_address1,primary_address2,primary_city,primary_zip,gender,age_bracket,geo_bucket,edu_level
"""

def get_settings(algorithm="leximin"):
    columns_to_keep = [
        "first_name",
        "last_name",
        "mobile_number",
        "email",
        "primary_address1",
        "primary_address2",
        "primary_city",
        "primary_zip",
        "gender",
        "age_bracket",
        "geo_bucket",
        "edu_level",
    ]
    return Settings(
        id_column="nationbuilder_id",
        columns_to_keep=columns_to_keep,
        check_same_address=True,
        check_same_address_columns=["primary_address1", "primary_zip"],
        max_attempts=100,
        selection_algorithm=algorithm,
        random_number_seed=0,
        json_file_path=Path.home() / "secret_do_not_commit.json",
    )


# TODO parametrize - each of the 4 algorithms - check coverage after that!
@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_csv_selection_happy_path_defaults(algorithm):
    """
    Objective: Check the happy path completes.
    Context: This test is meant to do what the use will do via the GUI when using a CSV file.
    Expectations: Given default settings and an easy selection, we should get selected and remaining.
    """
    settings = get_settings(algorithm)
    people_cats = PeopleAndCatsCSV()
    people_cats.load_cats(categories_content, "Categories", settings)
    people_cats.number_people_to_select = 22
    message = people_cats.load_people(settings, candidates_content, "Respondents", "Categories", "")
    print("load_people_message: ")
    print(message)
    success, output_lines = people_cats.people_cats_run_stratification(settings, False)
    # we are removing the header line with the [1:]
    selected_lines = [l.strip() for l in people_cats.get_selected_file().getvalue().split("\n") if l.strip()][1:]
    remaining_lines = [l.strip() for l in people_cats.get_remaining_file().getvalue().split("\n") if l.strip()][1:]
    """
		if success and self.PeopleAndCats.get_selected_file() is not None and self.PeopleAndCats.get_remaining_file() is not None:
			eel.enable_selected_download(self.PeopleAndCats.get_selected_file().getvalue(), 'selected.csv')
			eel.enable_remaining_download(self.PeopleAndCats.get_remaining_file().getvalue(), 'remaining.csv')
    """
    print(output_lines)
    assert success
    assert len(selected_lines) == 22
    # we have the -1 to remove the header
    assert len(selected_lines) + len(remaining_lines) == len(candidates_lines) - 1
