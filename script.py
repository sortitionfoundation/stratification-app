import platform
import sys

import eel
import gspread

from stratification import (
    PeopleAndCats,
    PeopleCatsCSV,
    PeopleCatsGoogleSheet,
    Settings,
)


class ScriptInitError(Exception):
    def __init__(self, classname: str) -> None:
        super().__init__(f"Not initialised {classname} yet")


# This class is now a GUI interface handler.
# all the "content" has been moved into the people_and_cats class and its children
class EventHandler:
    def __init__(self) -> None:
        self._people_and_cats: PeopleAndCats | None = None
        self._people_cats_csv: PeopleCatsCSV | None = None
        self._people_cats_g_sheet: PeopleCatsGoogleSheet | None = None
        self._settings = None
        # All of these below are only used in the Google Sheet version
        self.g_sheet_name = ""
        self.respondents_tab_name = "Respondents"  # Instance attribute for Advanced Settings
        self.category_tab_name = "Categories"  # Instance attribute for Advanced Settings
        self.gen_rem_tab = "on"  # Instance attribute for Advanced Settings
        self.number_selections = 1  # Instance attribute for Advanced Settings (then later stored in people_and_cats)

    @property
    def people_and_cats(self) -> PeopleAndCats:
        if not self._people_and_cats:
            raise ScriptInitError("PeopleAndCats")  # noqa: EM101
        return self._people_and_cats

    @property
    def people_cats_csv(self) -> PeopleCatsCSV:
        if not self._people_cats_csv:
            raise ScriptInitError("PeopleCatsCSV")  # noqa: EM101
        return self._people_cats_csv

    @property
    def people_cats_g_sheet(self) -> PeopleCatsGoogleSheet:
        if not self._people_cats_g_sheet:
            raise ScriptInitError("PeopleCatsGoogleSheet")  # noqa: EM101
        return self._people_cats_g_sheet

    @property
    def settings(self) -> Settings:
        self._init_settings()
        assert self._settings
        return self._settings

    def _init_settings(self) -> str:
        """
        Call from lots of places to report the error early
        """
        message = ""
        if self._settings is None:
            self._settings, message = Settings.load_from_file()
        return message

    def _add_g_sheet_category_content(self, g_sheet_name: str) -> None:
        min_selection = max_selection = 0
        all_msg: list[str] = []
        try:
            message = self._init_settings()
            if message != "":
                all_msg.append(message)
        # we want to catch and report unexpected exceptions here
        except Exception as error:  # noqa: BLE001
            self.people_and_cats.category_content_loaded = False
            all_msg.append(f"Error reading in settings file: {error}")
        try:
            msg2, min_selection, max_selection = self.people_cats_g_sheet.load_cats(
                self.people_and_cats,
                g_sheet_name,
                self.category_tab_name,
                self.settings,
            )
            all_msg += msg2
        except gspread.exceptions.APIError as error:
            all_msg.append(
                f"API error causing delay. Please wait a couple of seconds while g_sheet updates. "
                f"After waiting you may need to reload sheet. "
                f"For the record, the API error is {error}",
            )
        # we want to catch and report unexpected exceptions here
        except Exception as error:  # noqa: BLE001
            self.people_and_cats.category_content_loaded = False
            all_msg.append(f"Error reading in categories file: {error}")
            print(all_msg)
        eel.update_categories_output_area("<br />".join(all_msg))
        self.update_csv_selection_content()
        eel.update_selection_range(min_selection, max_selection)
        # if these are the same just set the value!
        if min_selection == max_selection and min_selection > 0:
            eel.set_select_number_people(str(min_selection))
            self.people_and_cats.number_people_to_select = min_selection
        # if we've already uploaded people, we need to re-process them with the
        # (possibly) new categories settings
        if self.people_and_cats.people_content_loaded:
            all_msg = self.people_cats_g_sheet.load_people(
                self.people_and_cats,
                self.settings,
                self.respondents_tab_name,
                self.category_tab_name,
                self.gen_rem_tab,
            )
            eel.update_selection_output_area("<br />".join(all_msg))
        self.update_run_button()

    # called from CSV input
    # note this is similar to the g_sheet version, but not entirely. Could consider
    # further refactoring to DRY if that seems warranted.
    def add_csv_category_content(self, file_contents: str) -> None:
        if file_contents == "":
            return
        self._people_cats_csv = PeopleCatsCSV()
        self._people_and_cats = PeopleAndCats(self._people_cats_csv)
        min_selection = max_selection = 0
        all_msg: list[str] = []
        try:
            message = self._init_settings()
            if message != "":
                all_msg.append(message)
        # we want to catch and report unexpected exceptions here
        except Exception as error:  # noqa: BLE001
            self.people_and_cats.category_content_loaded = False
            all_msg.append(f"Error reading in settings file: {error}")
        try:
            msg2, min_selection, max_selection = self.people_cats_csv.load_cats(self.people_and_cats, file_contents)
            all_msg += msg2
        # we want to catch and report unexpected exceptions here
        except Exception as error:  # noqa: BLE001
            self.people_and_cats.category_content_loaded = False
            all_msg.append(f"Error reading in categories file: {error}")
            print(all_msg)
        eel.update_categories_output_area("<br />".join(all_msg))
        self.update_csv_selection_content()
        eel.update_selection_range(min_selection, max_selection)
        # if these are the same just set the value!
        if min_selection == max_selection and min_selection > 0:
            eel.set_select_number_people(str(min_selection))
            self.people_and_cats.number_people_to_select = min_selection
        # if we've already uploaded people, we need to re-process them with the
        # (possibly) new categories settings
        if self.people_and_cats.people_content_loaded:
            all_msg += self.people_cats_csv.load_people(self.people_and_cats, self.settings)
            eel.update_selection_output_area("<br />".join(all_msg))
        self.update_run_button()

    def _clear_messages(self, normal_message="Number of categories: You must (re)load sheet..."):
        eel.update_categories_output_area(normal_message)
        eel.update_selection_output_area(normal_message)
        eel.update_selection_output_messages_area("")
        eel.set_select_number_people("")

    # called from g-sheet input
    def update_g_sheet_name(self, g_sheet_name_input):
        self._clear_messages()
        self.g_sheet_name = g_sheet_name_input
        if self.g_sheet_name != "":
            eel.enable_load_g_sheet_btn()
            # user has hit the (re)load button

    # do cats and people at same time...
    def load_g_sheet(self):
        # this can happen if they enter something and then delete it...
        if self.g_sheet_name == "":
            self._clear_messages("Please enter a spreadsheet name...")
        else:
            self._clear_messages("Requesting data from sheet...")
            try:
                self._people_cats_g_sheet = PeopleCatsGoogleSheet()
                self._people_and_cats = PeopleAndCats(self._people_cats_g_sheet)
                # tell this object what this currently is...
                self.people_and_cats.number_selections = self.number_selections
                all_msg: list[str] = []
                if self.number_selections > 1:
                    all_msg.append(
                        f"<b>WARNING</b>: You've asked for {self.number_selections} selections. "
                        f"You cannot use the <i>Produce a Test Panel</i> button if you want more "
                        f"than 1 selection and no Remaining tab will be created.",
                    )
                self._add_g_sheet_category_content(self.g_sheet_name)
                # TODO: this is also called in self._add_g_sheet_category_content() - we should delete one
                # probably this one to be consistent with add_csv_category_content()
                all_msg += self.people_cats_g_sheet.load_people(
                    self.people_and_cats,
                    self.settings,
                    self.respondents_tab_name,
                    self.category_tab_name,
                    self.gen_rem_tab,
                )
                eel.update_selection_output_area("<br />".join(all_msg))
                self.update_run_button()
                eel.enable_load_g_sheet_btn()
            except Exception as error:  # noqa: BLE001
                eel.update_categories_output_area(
                    f"Please wait a couple of seconds while g_sheet updates. "
                    f"After waiting you may need to reload sheet. Current error is: {error}",
                )

    ###############################################################################
    ### The next functions read in extra instance variables for advanced settings###
    ###############################################################################
    def update_respondents_tab_name(self, respondents_tab_name_input):
        self._clear_messages()
        self.respondents_tab_name = respondents_tab_name_input

    def update_g_sheet_categories_tab_name(self, categories_tab_name_input):
        self._clear_messages()
        self.category_tab_name = categories_tab_name_input

    def update_gen_rem_tab(self, gen_rem_tab_input):
        self.gen_rem_tab = gen_rem_tab_input
        # never generate a remaining tab if doing a multiple selection
        if self.number_selections > 1:
            self.gen_rem_tab = "off"

    def update_number_selections(self, number_selections_input):
        self._clear_messages()
        if number_selections_input == "":
            self.number_selections = 1
        else:
            self.number_selections = int(number_selections_input)
        # never generate a remaining tab if doing a multiple selection
        if self.number_selections > 1:
            self.gen_rem_tab = "off"
        # but turn it on if = 1 (this could be wrong if the person wants it off!)
        # if this has changed back to 1...
        else:
            self.gen_rem_tab = "on"

    ########################################
    ###End of Advanced Settings variables###
    ########################################
    ### From here 'selection' means people...
    def add_csv_selection_content(self, file_contents):
        self._init_settings()
        # this calls update internally
        msg = self.people_cats_csv.load_people(
            self.people_and_cats,
            self.settings,
            file_contents,
        )
        eel.update_selection_output_area("<br />".join(msg))
        self.update_run_button()

    # 'selection' means people...
    def update_csv_selection_content(self):
        if self.people_and_cats.category_content_loaded:
            eel.enable_csv_selection_content()

    def update_run_button(self):
        if (
            self.people_and_cats.category_content_loaded
            and self.people_and_cats.people_content_loaded
            and self.people_and_cats.number_people_to_select > 0
        ):
            eel.enable_run_button()
        else:
            eel.disable_run_button()
        if self.people_and_cats.number_people_to_select <= 0:
            eel.set_select_number_people("")

    def update_number_people(self, number_people):
        if number_people == "":
            self.people_and_cats.number_people_to_select = 0
        else:
            self.people_and_cats.number_people_to_select = int(number_people)
        self.update_run_button()

    def run_selection(self, test_selection: bool) -> None:
        self._init_settings()
        # they may have hit this button again, so clear the output area so it's more obvious
        eel.update_selection_output_messages_area("Selecting... please wait...<br />")
        success, output_lines = self.people_and_cats.people_cats_run_stratification(
            self.settings,
            test_selection,
        )
        if (
            success
            and self.people_and_cats.get_selected_file() is not None
            and self.people_and_cats.get_remaining_file() is not None
        ):
            eel.enable_selected_download(
                self.people_and_cats.get_selected_file().getvalue(),
                "selected.csv",
            )
            eel.enable_remaining_download(
                self.people_and_cats.get_remaining_file().getvalue(),
                "remaining.csv",
            )
        # print output_lines to the App:
        eel.update_selection_output_messages_area("<br />".join(output_lines))


# global to hold contents uploaded from JS
# not really - now just a GUI event handler more or less...
event_handler = EventHandler()


@eel.expose
def handle_csv_category_contents(file_contents):
    event_handler.add_csv_category_content(file_contents)


# 'selection' means people...
@eel.expose
def handle_csv_selection_contents(file_contents):
    event_handler.add_csv_selection_content(file_contents)


@eel.expose
def update_g_sheet_name(g_sheet_name):
    event_handler.update_g_sheet_name(g_sheet_name)


@eel.expose
def load_g_sheet():
    event_handler.load_g_sheet()


#############################
###Start Advanced Settings###
#############################
@eel.expose
def update_respondents_tab_name(respondents_tab_name):
    event_handler.update_respondents_tab_name(respondents_tab_name)


@eel.expose
def reload_respondents_tab():
    event_handler.update_respondents_tab_name("")


@eel.expose
def update_g_sheet_categories_tab_name(categories_tab_name):
    event_handler.update_g_sheet_categories_tab_name(categories_tab_name)


@eel.expose
def reload_categories_tab():
    event_handler.update_g_sheet_categories_tab_name("")


@eel.expose
def update_gen_rem_tab(gen_rem_tab):
    event_handler.update_gen_rem_tab(gen_rem_tab)


@eel.expose
def reload_gen_rem_tab():
    event_handler.update_gen_rem_tab("")


@eel.expose
def update_number_selections(number_selections):
    event_handler.update_number_selections(number_selections)


@eel.expose
def reload_number_selections():
    event_handler.update_number_selections("")


###########################
###End Advanced Settings###
###########################


@eel.expose
def update_number_people(number_people):
    event_handler.update_number_people(number_people)


@eel.expose
def run_selection():
    event_handler.run_selection(test_selection=False)


@eel.expose
def run_test_selection():
    event_handler.run_selection(test_selection=True)


MIN_WINDOWS_VERSION = 10


def main():
    default_size = (800, 800)
    eel.init("web")  # Give folder containing web files
    try:
        eel.start("main.html", size=default_size)
    except OSError:
        # on Windows 10 try Edge if Chrome not available
        if sys.platform in ("win32", "win64") and int(platform.release()) >= MIN_WINDOWS_VERSION:
            eel.start("main.html", mode="edge", size=default_size)
        else:
            raise


if __name__ == "__main__":
    main()
