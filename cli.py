import os

from stratification import (
    create_readable_sample_file,
    init_categories_people,
    print_category_selected,
    read_in_cats,
    run_stratification,
    write_selected_people_to_file,
)

# INPUT FILES etc:
root_io_dir = (
    # "/Users/bsh/brett/sortition/foundation/projects-events/Stratification-Services/python/"
    "/home/hamish/dev/sortition/brett-20190513/"
)

# first row MUST be fields named: category, name, min, max
# to randomly select one person, modify this file (and change total below to 1 !)
category_file_path = os.path.join(root_io_dir, "categories.csv")

# this file MUST have at least columns = id_column (below) AND those described in category file (other columns are ignored)
people_file_readable = root_io_dir + "example_people_readable.csv"

# OUTPUT FILE:
people_selected_file_name = root_io_dir + "example_people_readable-selected-final-22.csv"

# for testing - WARNING: will overwrite people_file_readable  file!
create_sample_file = False


def main():
    with open(category_file_path) as category_file:
        categories = read_in_cats(category_file)
    if create_sample_file:
        create_readable_sample_file(categories, people_file_readable)

    with open(people_file_readable, "r") as people_file:
        people, columns_data = init_categories_people(people_file, categories)

    success, tries, people_selected = run_stratification(categories, people, columns_data)

    print("Final:\n" + print_category_selected(categories))
    if success:
        print("We tried ", tries, " time(s).")
        print("Count = ", len(people_selected), " people selected")  # , people_selected
        # write selected people to a file
        with open(people_selected_file_name, mode="w") as selected_file:
            write_selected_people_to_file(people_selected, categories, columns_data, selected_file)
    else:
        print("Failed ", tries, " times... gave up.")


if __name__ == "__main__":
    main()
