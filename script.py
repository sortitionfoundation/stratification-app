import platform
import sys
from copy import deepcopy
from io import StringIO

import eel

from stratification import (
    get_selection_number_range,
    init_categories_people,
    read_in_cats,
    run_stratification,
    write_selected_people_to_file,
    NoSettingsFile,
    Settings,
)


class FileContents():

    def __init__(self):
        self.category_raw_content = ''
        self.selection_raw_content = ''
        self.original_categories = None
        self.categories_after_people = None
        self.columns_data = None
        self.people_file_contents = None
        self.people = None
        self.number_people_to_select = 0
        # mins and maxs (from category data) for number of people one can select
        self.min_max_people = {}
        self._settings = None

    @property
    def settings(self):
        self._init_settings()
        return self._settings

    def _init_settings(self):
        """
        Call from lots of places to report the error early
        """
        if self._settings is None:
            self._settings, message = Settings.load_from_file()
            if message:
                eel.alert_user(message, False)

    def add_category_content(self, file_contents):
        self._init_settings()
        csv_files.category_raw_content = file_contents
        category_file = StringIO(file_contents)
        try:
            self.original_categories, self.min_max_people = read_in_cats(category_file)
            msg = "Number of categories: {}".format(len(self.original_categories.keys()))
        except Exception as error:
            # put error in the GUI box !
            msg = "Error reading in categories: {}".format(error)
        eel.update_categories_output_area(msg)
        self.update_selection_content()
        min_selection, max_selection = get_selection_number_range(self.min_max_people)
        eel.update_selection_range(min_selection, max_selection)
        # if we've already uploaded people, we need to re-process them with the
        # (possibly) new categories settings
        if self.people_file_contents:
            self.update_people()
        self.update_run_button()

    def add_selection_content(self, file_contents):
        self._init_settings()
        csv_files.selection_raw_content = file_contents
        self.people_file_contents = file_contents
        self.update_people()
        self.update_run_button()

    def update_people(self):
        people_file = StringIO(self.people_file_contents)
        # init_categories_people() modifies the categories, so we need to
        # keep the original categories here
        self.categories_after_people = deepcopy(self.original_categories)
        try:
            self.people, self.columns_data, msg_list = init_categories_people(people_file, self.categories_after_people, self.settings)
            #print('in add_selection_content(), self.people: {}'.format(self.people))
            msg = "<br />".join(msg_list)
        except Exception as error:
            msg = "Error loading people: {}".format(error)
        eel.update_selection_output_area(msg)

    def update_selection_content(self):
        if self.category_raw_content:
            eel.enable_selection_content()

    def update_run_button(self):
        if self.category_raw_content and self.selection_raw_content and self.number_people_to_select > 0:
            eel.enable_run_button()

    def update_number_people(self, number_people):
        if number_people == '':
            self.number_people_to_select = 0
        else:
            self.number_people_to_select = int(number_people)
        self.update_run_button()

    def run_selection(self):
        self._init_settings()
        success, tries, people_selected, output_lines = run_stratification(
            self.categories_after_people, self.people, self.columns_data, self.number_people_to_select, self.min_max_people, self.settings
        )
        if success:
            selectfile = StringIO()
            remainfile = StringIO()
            output_lines += write_selected_people_to_file(self.people, people_selected, self.categories_after_people, self.columns_data, selectfile, remainfile, self.settings)
            eel.enable_selected_download(selectfile.getvalue(), 'selected.csv')
            eel.enable_remaining_download(remainfile.getvalue(), 'remaining.csv')
        # print output_lines to the App:
        eel.update_selection_output_messages_area("<br />".join(output_lines))


# global to hold contents uploaded from JS
csv_files = FileContents()


@eel.expose
def handle_category_contents(file_contents):
    csv_files.add_category_content(file_contents)


@eel.expose
def handle_selection_contents(file_contents):
    csv_files.add_selection_content(file_contents)


@eel.expose
def update_number_people(number_people):
    csv_files.update_number_people(number_people)


@eel.expose
def run_selection():
    csv_files.run_selection()


def main():
    default_size = (800, 800)
    eel.init('web')  # Give folder containing web files
    try:
        eel.start('main.html', size=default_size)
    except EnvironmentError:
        # on Windows 10 try Edge if Chrome not available
        if sys.platform in ('win32', 'win64') and int(platform.release()) >= 10:
            eel.start('main.html', mode='edge', size=default_size)
        else:
            raise


if __name__ == '__main__':
    main()
