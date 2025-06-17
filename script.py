from ast import Str
from io import StringIO
import platform
import sys
from pathlib import Path

import eel
import gspread
from sortition_algorithms import Settings, adapters, core, features, people

# from stratification import (
#     PeopleAndCatsCSV,
#     PeopleAndCatsGoogleSheet,
# )

DEFAULT_SETTINGS_PATH = Path.home() / "sf_stratification_settings.toml"
DEFAULT_AUTH_JSON_PATH = Path.home() / "sf_stratification_settings.toml"


class SettingsHolder:
    def __init__(self):
        self._settings: Settings | None = None

    @property
    def settings(self) -> Settings:
        self.init_settings()
        assert self._settings is not None
        return self._settings

    def init_settings(self) -> str:
        """
        Call from lots of places to report the error early
        """
        message = ""
        if self._settings is None:
            try:
                self._settings, message = Settings.load_from_file(
                    settings_file_path=DEFAULT_SETTINGS_PATH
                )
            except Exception as error:
                return f"Error reading in settings file: {error}"
        return message

    def loaded(self) -> bool:
        return self._settings is not None


settings_holder = SettingsHolder()


class CSVHandler:
    def __init__(self):
        self.adapter = adapters.CSVAdapter()
        self.features: features.FeatureCollection | None = None
        self.people: people.People | None = None
        # cache this in case we need to reload
        self.people_contents: str = ""
        self.panel_size: int = 0

    def add_feature_content(self, file_contents: str):
        all_msg: list[str] = []
        if not file_contents:
            all_msg.append("No file contents - was the file empty?")
            eel.update_csv_features_output_area("<br />".join(all_msg))
            return
        message = settings_holder.init_settings()
        if message:
            all_msg.append(message)
        if not settings_holder.loaded():
            eel.update_csv_features_output_area("<br />".join(all_msg))
            return
        try:
            self.features, msgs = self.adapter.load_features_from_str(file_contents)
            all_msg += msgs
        except Exception as error:
            all_msg.append(f"Failed to load features: {error}")
        eel.update_csv_features_output_area("<br />".join(all_msg))
        if not self.features:
            return
        eel.enable_csv_selection_content()
        min_size = self.features.minimum_selection()
        max_size = self.features.maximum_selection()
        eel.update_csv_selection_range(min_size, max_size)
        # if these are the same just set the value!
        if min_size == max_size and min_size > 0:
            eel.set_csv_panel_size(str(min_size))
            self.panel_size = min_size
        # reset people, might need to be reloaded with features
        if self.people:
            self.add_people_content(self.people_contents)

    def add_people_content(self, file_contents: str):
        all_msg: list[str] = []
        assert self.features is not None
        try:
            self.people, msgs = self.adapter.load_people_from_str(
                file_contents,
                settings_holder.settings,
                self.features,
            )
            # now we've done a successful load, cache the results
            self.people_contents = file_contents
            all_msg += msgs
        except Exception as error:
            all_msg.append(f"Failed to load people: {error}")
        eel.update_csv_selection_output_area("<br />".join(all_msg))
        self.update_run_button()

    def update_panel_size(self, panel_size: str) -> None:
        if panel_size == "":
            self.panel_size = 1
        else:
            self.panel_size = int(panel_size.strip())

    def update_run_button(self):
        if self.features and self.people and self.panel_size > 0:
            eel.enable_csv_run_button()
        else:
            eel.disable_csv_run_button()
        if self.panel_size <= 0:
            eel.set_csv_panel_size("")

    def run_selection(self, test_selection: bool):
        all_msg: list[str] = []
        assert self.people is not None and self.features is not None
        # they may have hit this button again, so clear the output area so it's more obvious
        eel.update_selection_output_messages_area("Selecting... please wait...<br />")
        success, people_selected, msgs = core.run_stratification(
            self.features,
            self.people,
            self.panel_size,
            settings_holder.settings,
            test_selection=test_selection,
        )
        all_msg += msgs
        selected_rows, remaining_rows, _ = core.selected_remaining_tables(
            self.people, people_selected[0], self.features, settings_holder.settings
        )
        if success:
            self.adapter.selected_file = StringIO()
            self.adapter.remaining_file = StringIO()
            self.adapter.output_selected_remaining(selected_rows, remaining_rows)
            eel.enable_csv_selected_download(
                self.adapter.selected_file.getvalue(),
                "selected.csv",
            )
            eel.enable_csv_remaining_download(
                self.adapter.remaining_file.getvalue(),
                "remaining.csv",
            )
        # print output_lines to the App:
        eel.update_selection_output_messages_area("<br />".join(all_msg))


class GSheetHandler:
    clear_message = "Number of features: You must (re)load sheet..."

    def __init__(self):
        self.adapter = adapters.GSheetAdapter(DEFAULT_AUTH_JSON_PATH)
        self.features: features.FeatureCollection | None = None
        self.people: people.People | None = None
        self.panel_size: int = 0

    def _clear_messages(self, normal_message: str = clear_message):
        eel.update_g_sheet_features_output_area(normal_message)
        eel.update_g_sheet_selection_output_area(normal_message)
        eel.update_selection_output_messages_area("")
        eel.set_g_sheet_panel_size("")

    def add_feature_content(self, g_sheet_name: str, feature_tab_name: str):
        all_msg: list[str] = []
        message = settings_holder.init_settings()
        if message:
            all_msg.append(message)
        if not settings_holder.loaded():
            eel.update_g_sheet_features_output_area("<br />".join(all_msg))
            return
        try:
            self.features, msgs = self.adapter.load_features(
                g_sheet_name, feature_tab_name
            )
            all_msg += msgs
        except gspread.exceptions.APIError as error:
            all_msg.append(
                f"API error causing delay. Please wait a couple of seconds while gsheet updates. "
                f"After waiting you may need to reload sheet. "
                f"For the record, the API error is {error}",
            )
        except Exception as error:
            all_msg.append(f"Failed to load features: {error}")
        if not self.features:
            all_msg.append("Failed to load features")
        eel.update_g_sheet_features_output_area("<br />".join(all_msg))
        if self.features:
            eel.update_g_sheet_selection_range(
                self.features.minimum_selection(), self.features.maximum_selection()
            )

    def add_people_content(self, people_tab_name: str):
        all_msg: list[str] = []
        assert self.features is not None
        try:
            self.people, msgs = self.adapter.load_people(
                people_tab_name,
                settings_holder.settings,
                self.features,
            )
            all_msg += msgs
        except Exception as error:
            all_msg.append(f"Failed to load people: {error}")
        if not self.people:
            all_msg.append("Failed to load people")
        eel.update_g_sheet_selection_output_area("<br />".join(all_msg))

    """
    success, people_selected, msgs = core.run_stratification(features, people, number_wanted, settings_obj)
    echo_all(msgs)
    if not success:
        raise click.ClickException("Selection not successful, no files written.")

    selected_rows, remaining_rows, _ = core.selected_remaining_tables(
        people, people_selected[0], features, settings_obj
    )
    adapter.selected_tab_name = selected_tab_name
    adapter.remaining_tab_name = remaining_tab_name
    adapter.output_selected_remaining(selected_rows, remaining_rows, settings_obj)
    """


# to be honest this is no longer a file contents class - it's a GUI interface handler
# all the "content" has been moved into the PeopleAndCats class and its children
class FileContents:
    def __init__(self):
        self.PeopleAndCats = None
        # All of these below are only used in the Google Sheet version
        self.g_sheet_name = ""
        self.respondents_tab_name = (
            "Respondents"  # Instance attribute for Advanced Settings
        )
        self.category_tab_name = (
            "Categories"  # Instance attribute for Advanced Settings
        )
        self.gen_rem_tab = "on"  # Instance attribute for Advanced Settings
        self.number_selections = 1  # Instance attribute for Advanced Settings (then later stored in PeopleAndCats)

    def _add_category_content(self, input_content):
        min_selection = 0
        max_selection = 0
        all_msg: list[str] = []
        try:
            message = self._init_settings()
            if message != "":
                all_msg.append(message)
        # we want to catch and report unexpected exceptions here
        except Exception as error:  # noqa: BLE001
            self.PeopleAndCats.category_content_loaded = False
            all_msg.append(f"Error reading in settings file: {error}")
        try:
            msg2, min_selection, max_selection = self.PeopleAndCats.load_cats(
                input_content,
                self.category_tab_name,
                self._settings,
            )
            all_msg += msg2
        except gspread.exceptions.APIError as error:
            all_msg.append(
                f"API error causing delay. Please wait a couple of seconds while gsheet updates. "
                f"After waiting you may need to reload sheet. "
                f"For the record, the API error is {error}",
            )
        # we want to catch and report unexpected exceptions here
        except Exception as error:  # noqa: BLE001
            self.PeopleAndCats.category_content_loaded = False
            all_msg.append(f"Error reading in categories file: {error}")
            print(all_msg)  # noqa: T201
        eel.update_categories_output_area("<br />".join(all_msg))
        self.update_selection_content()
        eel.update_selection_range(min_selection, max_selection)
        # if these are the same just set the value!
        if min_selection == max_selection and min_selection > 0:
            eel.set_select_number_people(str(min_selection))
            self.PeopleAndCats.number_people_to_select = int(min_selection)
        # if we've already uploaded people, we need to re-process them with the
        # (possibly) new categories settings
        if self.PeopleAndCats.people_content_loaded:
            dummy_file_contents = ""
            all_msg = self.PeopleAndCats.load_people(
                self.settings,
                dummy_file_contents,
                self.respondents_tab_name,
                self.category_tab_name,
                self.gen_rem_tab,
            )
            eel.update_selection_output_area("<br />".join(all_msg))
        self.update_run_button()

    # called from CSV input
    def add_category_content(self, file_contents):
        if file_contents != "":
            self.PeopleAndCats = PeopleAndCatsCSV()
            self._add_category_content(file_contents)

    def _clear_messages(
        self, normal_message="Number of categories: You must (re)load sheet..."
    ):
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
                self.PeopleAndCats = PeopleAndCatsGoogleSheet()
                # tell this object what this currently is...
                self.PeopleAndCats.number_selections = self.number_selections
                all_msg: list[str] = []
                if self.number_selections > 1:
                    all_msg.append(
                        f"<b>WARNING</b>: You've asked for {self.number_selections} selections. "
                        f"You cannot use the <i>Produce a Test Panel</i> button if you want more "
                        f"than 1 selection and no Remaining tab will be created.",
                    )
                self._add_category_content(self.g_sheet_name)
                dummy_file_contents = ""
                all_msg += self.PeopleAndCats.load_people(
                    self.settings,
                    dummy_file_contents,
                    self.respondents_tab_name,
                    self.category_tab_name,
                    self.gen_rem_tab,
                )
                eel.update_selection_output_area("<br />".join(all_msg))
                self.update_run_button()
                eel.enable_load_g_sheet_btn()
            except Exception as error:  # noqa: BLE001
                eel.update_categories_output_area(
                    f"Please wait a couple of seconds while gsheet updates. "
                    f"After waiting you may need to reload sheet. Current error is: {error}",
                )

    ###############################################################################
    ### The next functions read in extra instance variables for advanced settings###
    ###############################################################################
    def update_respondents_tab_name(self, respondents_tab_name_input):
        self._clear_messages()
        self.respondents_tab_name = respondents_tab_name_input

    def update_categories_tab_name(self, categories_tab_name_input):
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
    def add_selection_content(self, file_contents):
        self._init_settings()
        # this calls update internally
        msg = self.PeopleAndCats.load_people(
            self.settings,
            file_contents,
            self.respondents_tab_name,
            self.category_tab_name,
            self.gen_rem_tab,
        )
        eel.update_selection_output_area("<br />".join(msg))
        self.update_run_button()

    # 'selection' means people...
    def update_selection_content(self):
        if self.PeopleAndCats.category_content_loaded:
            eel.enable_selection_content()

    def update_run_button(self):
        if (
            self.PeopleAndCats.category_content_loaded
            and self.PeopleAndCats.people_content_loaded
            and self.PeopleAndCats.number_people_to_select > 0
        ):
            eel.enable_run_button()
        else:
            eel.disable_run_button()
        if self.PeopleAndCats.number_people_to_select <= 0:
            eel.set_select_number_people("")

    def update_number_people(self, number_people):
        if number_people == "":
            self.PeopleAndCats.number_people_to_select = 0
        else:
            self.PeopleAndCats.number_people_to_select = int(number_people)
        self.update_run_button()

    def run_selection(self, test_selection):
        self._init_settings()
        # they may have hit this button again, so clear the output area so it's more obvious
        eel.update_selection_output_messages_area("Selecting... please wait...<br />")
        success, output_lines = self.PeopleAndCats.people_cats_run_stratification(
            self.settings,
            test_selection,
        )
        if (
            success
            and self.PeopleAndCats.get_selected_file() is not None
            and self.PeopleAndCats.get_remaining_file() is not None
        ):
            eel.enable_selected_download(
                self.PeopleAndCats.get_selected_file().getvalue(),
                "selected.csv",
            )
            eel.enable_remaining_download(
                self.PeopleAndCats.get_remaining_file().getvalue(),
                "remaining.csv",
            )
        # print output_lines to the App:
        eel.update_selection_output_messages_area("<br />".join(output_lines))


# global to hold contents uploaded from JS
# not really - now just a GUI event handler more or less...
csv_files = FileContents()
csv_handler = CSVHandler()
g_sheet_handler = GSheetHandler()


#######################
# CSV functions for eel
#######################


@eel.expose
def handle_csv_file_features_content(file_contents):
    csv_handler.add_feature_content(file_contents)


# 'selection' means people...
@eel.expose
def handle_csv_file_people_content(file_contents):
    csv_handler.add_people_content(file_contents)


@eel.expose
def update_csv_panel_size(panel_size):
    csv_handler.update_panel_size(panel_size)


@eel.expose
def csv_run_selection():
    csv_handler.run_selection(test_selection=False)


@eel.expose
def csv_run_test_selection():
    csv_handler.run_selection(test_selection=True)


###########################
# G Sheet functions for eel
###########################


@eel.expose
def update_g_sheet_name(g_sheet_name):
    g_sheet_handler.update_g_sheet_name(g_sheet_name)


@eel.expose
def load_g_sheet():
    g_sheet_handler.load_g_sheet()


#############################
###Start Advanced Settings###
#############################
@eel.expose
def update_respondents_tab_name(respondents_tab_name):
    g_sheet_handler.update_respondents_tab_name(respondents_tab_name)


@eel.expose
def reload_respondents_tab():
    g_sheet_handler.update_respondents_tab_name("")


@eel.expose
def update_categories_tab_name(categories_tab_name):
    g_sheet_handler.update_categories_tab_name(categories_tab_name)


@eel.expose
def reload_categories_tab():
    g_sheet_handler.update_categories_tab_name("")


@eel.expose
def update_gen_rem_tab(gen_rem_tab):
    g_sheet_handler.update_gen_rem_tab(gen_rem_tab)


@eel.expose
def reload_gen_rem_tab():
    g_sheet_handler.update_gen_rem_tab("")


@eel.expose
def update_number_selections(number_selections):
    g_sheet_handler.update_number_selections(number_selections)


@eel.expose
def reload_number_selections():
    g_sheet_handler.update_number_selections("")


###########################
###End Advanced Settings###
###########################


@eel.expose
def update_number_people(number_people):
    g_sheet_handler.update_number_people(number_people)


@eel.expose
def run_selection():
    g_sheet_handler.run_selection(test_selection=False)


@eel.expose
def run_test_selection():
    g_sheet_handler.run_selection(test_selection=True)


MIN_WINDOWS_VERSION = 10


def main():
    default_size = (800, 800)
    eel.init("web")  # Give folder containing web files
    try:
        eel.start("main.html", size=default_size)
    except OSError:
        # on Windows 10 try Edge if Chrome not available
        if (
            sys.platform in ("win32", "win64")
            and int(platform.release()) >= MIN_WINDOWS_VERSION
        ):
            eel.start("main.html", mode="edge", size=default_size)
        else:
            raise


if __name__ == "__main__":
    main()
