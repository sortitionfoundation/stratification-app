import platform
import sys
from collections.abc import Iterable
from enum import Enum
from pathlib import Path

import eel
import gspread
from sortition_algorithms import Settings, adapters, core, features, people

DEFAULT_SETTINGS_PATH = Path.home() / "sf_stratification_settings.toml"
DEFAULT_AUTH_JSON_PATH = Path.home() / "secret_do_not_commit.json"


class LogType(Enum):
    CSV_FEATURES = 1
    CSV_SELECTION = 2
    GSHEET_FEATURES = 3
    GSHEET_SELECTION = 4
    DETAILED_LOG = 5


class GuiLog:
    """Singleton class for sending messages to different divs"""

    def __init__(self) -> None:
        self.lines: dict[LogType, list[str]] = {lt: [""] for lt in LogType}

    def reset(self, section: LogType, new_message: str = "") -> None:
        self.lines[section] = [new_message]
        self.update_area(section)

    def add_lines(self, section: LogType, lines: Iterable[str]) -> None:
        self.lines[section] += lines
        self.update_area(section)

    def add_line(self, section: LogType, line: str) -> None:
        self.lines[section].append(line)
        self.update_area(section)

    def update_area(self, section: LogType) -> None:
        update_str = "<br />".join(line for line in self.lines[section] if line.strip())
        if section == LogType.CSV_FEATURES:
            eel.update_csv_features_output_area(update_str)
        elif section == LogType.CSV_SELECTION:
            eel.update_csv_selection_output_area(update_str)
        elif section == LogType.GSHEET_FEATURES:
            eel.update_g_sheet_features_output_area(update_str)
        elif section == LogType.GSHEET_SELECTION:
            eel.update_g_sheet_selection_output_area(update_str)
        elif section == LogType.DETAILED_LOG:
            eel.update_detailed_log_messages_area(update_str)

    def update_all_areas(self) -> None:
        for log_type in LogType:
            self.update_area(log_type)


gui_log = GuiLog()


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
        if self._settings is None:
            try:
                self._settings, report = Settings.load_from_file(
                    settings_file_path=DEFAULT_SETTINGS_PATH,
                )
                return report.as_html()
            except Exception as error:
                return f"Error reading in settings file: {error}"
        return ""

    def init_settings_log(self, section: LogType) -> None:
        message = self.init_settings()
        if message:
            gui_log.add_line(section, message)

    def loaded(self) -> bool:
        return self._settings is not None


settings_holder = SettingsHolder()


class CSVHandler:
    def __init__(self):
        self.data_source = adapters.CSVStringDataSource("", "")
        self.select_data = adapters.SelectionData(self.data_source)
        self.features: features.FeatureCollection | None = None
        self.people: people.People | None = None
        # cache this in case we need to reload
        self.people_contents: str = ""
        self.panel_size_str = "0"  # Number of people in each panel

    @property
    def panel_size_num(self) -> int:
        if self.panel_size_str == "":
            return 0
        return int(self.panel_size_str)

    def _set_panel_size(self, panel_size: str | int, *, update_eel: bool = True) -> None:
        self.panel_size_str = str(panel_size)
        # check if we can convert to int, and that it is >= 0
        try:
            panel_size_int = int(self.panel_size_str)
            if panel_size_int < 0:
                self.panel_size_str = ""
        except ValueError:
            self.panel_size_str = ""
        # finally update the display - unless we've been called from the JS
        # in which case skip this to avoid infinite loops.
        if update_eel:
            eel.set_csv_panel_size(self.panel_size_str)

    def update_panel_size(self, panel_size: str) -> None:
        # this comes from the UI, so don't update_eel - otherwise we have a loop
        self._set_panel_size(panel_size.strip(), update_eel=False)
        self.update_run_button()

    def update_run_button(self):
        if self.features and self.people and self.panel_size_num > 0:
            eel.enable_csv_run_button()
        else:
            eel.disable_csv_run_button()

    def add_feature_content(self, file_contents: str):
        gui_log.reset(LogType.CSV_FEATURES)
        if not file_contents:
            gui_log.add_line(
                LogType.CSV_FEATURES,
                "No file contents - was the file empty?",
            )
            return
        settings_holder.init_settings_log(LogType.CSV_FEATURES)
        if not settings_holder.loaded():
            return
        try:
            self.data_source.features_data = file_contents
            self.features, report = self.select_data.load_features()
            gui_log.add_line(LogType.CSV_FEATURES, report.as_html())
        except Exception as error:
            gui_log.add_line(LogType.CSV_FEATURES, f"Failed to load features: {error}")
        if not self.features:
            return
        eel.enable_csv_selection_content()
        min_size = features.minimum_selection(self.features)
        max_size = features.maximum_selection(self.features)
        eel.update_csv_selection_range(min_size, max_size)
        # if these are the same just set the value!
        if min_size == max_size and min_size > 0:
            self._set_panel_size(min_size)
        # reset people, might need to be reloaded with features
        if self.people:
            self.add_people_content(self.people_contents)

    def add_people_content(self, file_contents: str) -> None:
        gui_log.reset(LogType.CSV_SELECTION)
        assert self.features is not None
        try:
            self.data_source.people_data = file_contents
            self.people, report = self.select_data.load_people(settings_holder.settings, self.features)
            # now we've done a successful load, cache the results
            self.people_contents = file_contents
            gui_log.add_line(LogType.CSV_SELECTION, report.as_html())
            gui_log.add_line(
                LogType.CSV_SELECTION,
                f"Loaded {self.people.count} people.",
            )
            gui_log.add_line(LogType.CSV_SELECTION, "Successfully loaded features and people.")
        except Exception as error:
            gui_log.add_line(LogType.CSV_SELECTION, f"Failed to load people: {error}")
        self.update_run_button()

    def run_selection(self, test_selection: bool) -> None:
        assert self.people is not None and self.features is not None
        # they may have hit this button again, so clear the output area so it's more obvious
        gui_log.reset(LogType.DETAILED_LOG, "Selecting... please wait...<br />")
        try:
            success, people_selected, report = core.run_stratification(
                self.features,
                self.people,
                self.panel_size_num,
                settings_holder.settings,
                test_selection=test_selection,
            )
        except Exception as err:
            gui_log.add_lines(
                LogType.DETAILED_LOG,
                [f"Unexpected error during selection: {err}", "Selection failed, process ended."],
            )
            return
        gui_log.add_line(LogType.DETAILED_LOG, report.as_html())
        if not success:
            gui_log.add_line(LogType.DETAILED_LOG, "No panels written to CSV, process ended.")
            return
        try:
            selected_rows, remaining_rows, _ = core.selected_remaining_tables(
                self.people,
                people_selected[0],
                self.features,
                settings_holder.settings,
            )
            if success:
                self.select_data.output_selected_remaining(selected_rows, remaining_rows, settings_holder.settings)
                eel.enable_csv_selected_download(
                    self.data_source.selected_file.getvalue(),
                    "selected.csv",
                )
                eel.enable_csv_remaining_download(
                    self.data_source.remaining_file.getvalue(),
                    "remaining.csv",
                )
        except Exception as err:
            gui_log.add_lines(
                LogType.DETAILED_LOG,
                [f"Unexpected error during writing selection: {err}", "Writing failed, process ended."],
            )


class GSheetHandler:
    clear_message = "Number of features: You must (re)load sheet..."
    original_selected_tab_name = "Original Selected - output - "
    remaining_tab_name = "Remaining - output - "

    def __init__(self):
        self.data_source = adapters.GSheetDataSource("", "", DEFAULT_AUTH_JSON_PATH)
        self.select_data = adapters.SelectionData(self.data_source)
        self.features: features.FeatureCollection | None = None
        self.people: people.People | None = None
        self.g_sheet_name = ""
        self.features_tab_name = "Categories"
        self.people_tab_name = "Respondents"
        self.gen_rem_tab = True
        self.number_selections = 1  # How many panels to create
        self.panel_size_str = "0"  # Number of people in each panel

    @property
    def panel_size_num(self) -> int:
        if self.panel_size_str == "":
            return 0
        return int(self.panel_size_str)

    def _set_panel_size(self, panel_size: str | int, *, update_eel: bool = True) -> None:
        self.panel_size_str = str(panel_size)
        # check if we can convert to int, and that it is >= 0
        try:
            panel_size_int = int(self.panel_size_str)
            if panel_size_int < 0:
                self.panel_size_str = ""
        except ValueError:
            self.panel_size_str = ""
        # finally update the display - unless we've been called from the JS
        # in which case skip this to avoid infinite loops.
        if update_eel:
            eel.set_g_sheet_panel_size(self.panel_size_str)

    def _clear_messages(self, normal_message: str = clear_message) -> None:
        """Clear all messages (and optionally put a new message in place)"""
        gui_log.reset(LogType.GSHEET_FEATURES, normal_message)
        gui_log.reset(LogType.GSHEET_SELECTION, normal_message)
        gui_log.reset(LogType.DETAILED_LOG)
        self._set_panel_size("")

    def _reset_spreadsheet(self, *, reset_features: bool = True) -> None:
        if reset_features:
            self.features = None
        self.people = None
        self._set_panel_size("")
        self.update_run_button()

    # called from g-sheet input
    def update_g_sheet_name(self, g_sheet_name_input) -> None:
        self._clear_messages()
        self._reset_spreadsheet()
        self.g_sheet_name = g_sheet_name_input
        if self.g_sheet_name != "":
            eel.enable_load_g_sheet_btn()

    def update_panel_size(self, panel_size: str) -> None:
        # this comes from the UI, so don't update_eel - otherwise we have a loop
        self._set_panel_size(panel_size.strip(), update_eel=False)
        self.update_run_button()

    def update_run_button(self) -> None:
        if self.features and self.people and self.panel_size_num > 0:
            eel.enable_g_sheet_run_button()
        else:
            eel.disable_g_sheet_run_button()

    def update_people_tab_name(self, people_tab_name_input: str) -> None:
        self._clear_messages()
        self._reset_spreadsheet(reset_features=False)
        self.people_tab_name = people_tab_name_input

    def update_features_tab_name(self, features_tab_name_input: str) -> None:
        self._clear_messages()
        self._reset_spreadsheet()
        self.features_tab_name = features_tab_name_input

    def update_gen_rem_tab(self, gen_rem_tab: bool) -> None:
        self.gen_rem_tab = gen_rem_tab

    def _safe_gen_rem_tab(self) -> bool:
        """Get self.gen_rem_tab - but set to false if number_selections > 1"""
        # never generate a remaining tab if doing a multiple selection
        if self.number_selections > 1:
            return False
        return self.gen_rem_tab

    def update_number_selections(self, number_selections_input: str) -> None:
        self._clear_messages()
        self.number_selections = 1 if number_selections_input == "" else int(number_selections_input)

    # do features and people at same time...
    def load_g_sheet(self) -> None:
        # this can happen if they enter something and then delete it...
        if self.g_sheet_name == "":
            self._clear_messages("Please enter a spreadsheet name...")
            return
        self._clear_messages("Requesting data from sheet...")
        settings_holder.init_settings_log(LogType.GSHEET_FEATURES)
        if not settings_holder.loaded():
            return
        try:
            if self.number_selections > 1:
                gui_log.add_line(
                    LogType.GSHEET_SELECTION,
                    f"<b>WARNING</b>: You've asked for {self.number_selections} selections. "
                    f"You cannot use the <i>Produce a Test Panel</i> button if you want more "
                    f"than 1 selection and no Remaining tab will be created.",
                )
            self.data_source.set_g_sheet_name(self.g_sheet_name)
            self.add_feature_content(self.features_tab_name)
            self.add_people_content(self.people_tab_name)
            gui_log.add_line(LogType.GSHEET_SELECTION, "Successfully loaded features and people.")
            self.update_run_button()
            eel.enable_load_g_sheet_btn()
        except Exception as error:
            gui_log.add_line(
                LogType.GSHEET_FEATURES,
                f"Please wait a couple of seconds while gsheet updates. "
                f"After waiting you may need to reload sheet. Current error is: {error}",
            )

    def add_feature_content(self, features_tab_name: str) -> None:
        try:
            self.data_source.feature_tab_name = features_tab_name
            self.features, report = self.select_data.load_features()
            gui_log.add_line(LogType.GSHEET_FEATURES, report.as_html())
        except gspread.exceptions.APIError as error:
            gui_log.add_line(
                LogType.GSHEET_FEATURES,
                f"API error causing delay. Please wait a couple of seconds while gsheet updates. "
                f"After waiting you may need to reload sheet. "
                f"For the record, the API error is {error}",
            )
        except Exception as error:
            gui_log.add_line(
                LogType.GSHEET_FEATURES,
                f"Failed to load features: {error}",
            )
        if not self.features:
            gui_log.add_line(
                LogType.GSHEET_FEATURES,
                "Failed to load features",
            )
            return
        eel.update_g_sheet_selection_range(
            features.minimum_selection(self.features),
            features.maximum_selection(self.features),
        )
        min_size = features.minimum_selection(self.features)
        max_size = features.maximum_selection(self.features)
        eel.update_g_sheet_selection_range(min_size, max_size)
        # if these are the same just set the value!
        if min_size == max_size and min_size > 0:
            self._set_panel_size(min_size)

    def add_people_content(self, people_tab_name: str) -> None:
        assert self.features is not None
        try:
            self.data_source.people_tab_name = people_tab_name
            self.people, report = self.select_data.load_people(settings_holder.settings, self.features)
            gui_log.add_line(LogType.GSHEET_SELECTION, report.as_html())
        except Exception as error:
            gui_log.add_line(
                LogType.GSHEET_SELECTION,
                f"Failed to load people: {error}",
            )
        if not self.people:
            gui_log.add_line(
                LogType.GSHEET_SELECTION,
                "Failed to load people",
            )

    def run_selection(self, test_selection: bool) -> None:
        assert self.features is not None and self.people is not None
        gui_log.reset(LogType.DETAILED_LOG, "Selecting... please wait...<br />")
        try:
            success, people_selected, report = core.run_stratification(
                self.features,
                self.people,
                self.panel_size_num,
                settings_holder.settings,
                test_selection=test_selection,
                number_selections=self.number_selections,
            )
        except Exception as err:
            gui_log.add_lines(
                LogType.DETAILED_LOG,
                [f"Unexpected error during selection: {err}", "Selection failed, process ended."],
            )
            return
        gui_log.add_line(LogType.DETAILED_LOG, report.as_html())
        if not success:
            gui_log.add_line(LogType.DETAILED_LOG, "No panels written to spreadsheet, process ended.")
            return

        gui_log.add_line(LogType.DETAILED_LOG, "About to write to spreadsheet.")
        try:
            selected_rows, remaining_rows, _ = core.selected_remaining_tables(
                self.people,
                people_selected[0],
                self.features,
                settings_holder.settings,
            )
            self.data_source.selected_tab_name = self.original_selected_tab_name
            self.data_source.remaining_tab_name = self.remaining_tab_name
            self.select_data.gen_rem_tab = self._safe_gen_rem_tab()
            self.select_data.output_selected_remaining(selected_rows, remaining_rows, settings_holder.settings)
            gui_log.add_line(LogType.DETAILED_LOG, "All spreadsheet writing has finished.")
            gui_log.add_line(LogType.DETAILED_LOG, "Selection process finished.")
        except Exception as err:
            gui_log.add_lines(
                LogType.DETAILED_LOG,
                [f"Unexpected error during writing selection: {err}", "Writing failed, process ended."],
            )


# globals - GUI event handlers
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
def update_respondents_tab_name(people_tab_name):
    g_sheet_handler.update_people_tab_name(people_tab_name)


@eel.expose
def reload_respondents_tab():
    g_sheet_handler.update_people_tab_name("")


@eel.expose
def update_features_tab_name(features_tab_name):
    g_sheet_handler.update_features_tab_name(features_tab_name)


@eel.expose
def reload_features_tab():
    g_sheet_handler.update_features_tab_name("")


@eel.expose
def update_gen_rem_tab(gen_rem_tab):
    g_sheet_handler.update_gen_rem_tab(gen_rem_tab)


@eel.expose
def reload_gen_rem_tab():
    g_sheet_handler.update_gen_rem_tab(gen_rem_tab=False)


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
def update_g_sheet_panel_size(panel_size):
    g_sheet_handler.update_panel_size(panel_size)


@eel.expose
def g_sheet_run_selection():
    g_sheet_handler.run_selection(test_selection=False)


@eel.expose
def g_sheet_run_test_selection():
    g_sheet_handler.run_selection(test_selection=True)


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
