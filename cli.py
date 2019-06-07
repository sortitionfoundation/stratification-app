from pathlib import Path

from stratification import (
    create_readable_sample_file,
    init_categories_people,
    print_category_selected,
    read_in_cats,
    run_stratification,
    write_selected_people_to_file,
)

# INPUT FILES etc:
root_io_dir = Path(
    "/Users/bsh/brett/sortition/foundation/projects-events/Stratification-Services/python/"
    #"/home/hamish/dev/sortition/brett-20190513/"
)

# first row MUST be fields named: category, name, min, max
# to randomly select one person, modify this file (and change total below to 1 !)
category_file_path = root_io_dir / "categories.csv"

# this file MUST have at least columns = id_column (below) AND those described
# in category file (other columns are ignored)
people_file_path = root_io_dir / "example_people_readable.csv"

# OUTPUT FILES:
people_selected_file_path = root_io_dir / "example_people_readable-selected-final-new-22.csv"
people_remaining_file_path = root_io_dir / "example_people_readable-selected-final-new-22-remaining.csv"

# for testing - WARNING: will overwrite people_file_path  file!
create_sample_file = False


def main():
    with open(category_file_path) as category_file:
        categories = read_in_cats(category_file)
    if create_sample_file:
        with open(people_file_path, "w") as people_file:
            create_readable_sample_file(categories, people_file)

    with open(people_file_path, "r") as people_file:
        people, columns_data = init_categories_people(people_file, categories)

    success, tries, people_selected = run_stratification(categories, people, columns_data)

    print("Final:\n" + print_category_selected(categories))
    if success:
        print(f"We tried {tries} time(s).")
        print("Count = ", len(people_selected), " people selected")  # , people_selected
        # write selected people to a file
        with open(people_selected_file_path, mode="w") as selected_file, open(people_remaining_file_path, mode="w") as remaining_file:
            write_selected_people_to_file(people, people_selected, categories, columns_data, selected_file, remaining_file)
    else:
        print(f"Failed {tries} times... gave up.")


if __name__ == "__main__":
    main()
