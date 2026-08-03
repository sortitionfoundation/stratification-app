# ABOUTME: The eel entry point - wires the browser UI to the session layer in strat_app.
# ABOUTME: Temporary, kept only so the old app runs alongside the Qt one during the port.

import platform
import sys

import eel

from eel_views import EelCsvView, EelGSheetView, EelLogView
from strat_app.sessions.csv_session import CsvSession
from strat_app.sessions.gsheet_session import GSheetSession
from strat_app.sessions.log import GuiLog
from strat_app.settings_holder import SettingsHolder

gui_log = GuiLog(EelLogView())
settings_holder = SettingsHolder()
csv_session = CsvSession(EelCsvView(), gui_log, settings_holder)
g_sheet_session = GSheetSession(EelGSheetView(), gui_log, settings_holder)


def panel_size_from_input(panel_size: str) -> int:
    """
    Turn what the user typed into a panel size.

    The browser UI uses a free text box, so anything at all can arrive here. Zero means
    "no valid size", which leaves the run button disabled.
    """
    try:
        size = int(panel_size.strip())
    except ValueError:
        return 0
    return max(size, 0)


#######################
# CSV functions for eel
#######################


@eel.expose
def handle_csv_file_features_content(file_contents):
    csv_session.add_feature_content(file_contents)


# 'selection' means people...
@eel.expose
def handle_csv_file_people_content(file_contents):
    csv_session.add_people_content(file_contents)


@eel.expose
def update_csv_panel_size(panel_size):
    csv_session.set_panel_size(panel_size_from_input(panel_size))


@eel.expose
def csv_run_selection():
    csv_session.run_selection(test_selection=False)


@eel.expose
def csv_run_test_selection():
    csv_session.run_selection(test_selection=True)


###########################
# G Sheet functions for eel
###########################


@eel.expose
def update_g_sheet_name(g_sheet_name):
    g_sheet_session.update_g_sheet_name(g_sheet_name)


@eel.expose
def load_g_sheet():
    g_sheet_session.load_g_sheet()


#############################
###Start Advanced Settings###
#############################
@eel.expose
def update_respondents_tab_name(people_tab_name):
    g_sheet_session.update_people_tab_name(people_tab_name)


@eel.expose
def reload_respondents_tab():
    g_sheet_session.update_people_tab_name("")


@eel.expose
def update_features_tab_name(features_tab_name):
    g_sheet_session.update_features_tab_name(features_tab_name)


@eel.expose
def reload_features_tab():
    g_sheet_session.update_features_tab_name("")


@eel.expose
def update_gen_rem_tab(gen_rem_tab):
    g_sheet_session.update_gen_rem_tab(gen_rem_tab)


@eel.expose
def reload_gen_rem_tab():
    g_sheet_session.update_gen_rem_tab(gen_rem_tab=False)


@eel.expose
def update_number_selections(number_selections):
    g_sheet_session.set_number_selections(1 if number_selections == "" else int(number_selections))


@eel.expose
def reload_number_selections():
    g_sheet_session.set_number_selections(1)


###########################
###End Advanced Settings###
###########################


@eel.expose
def update_g_sheet_panel_size(panel_size):
    g_sheet_session.set_panel_size(panel_size_from_input(panel_size))


@eel.expose
def g_sheet_run_selection():
    g_sheet_session.run_selection(test_selection=False)


@eel.expose
def g_sheet_run_test_selection():
    g_sheet_session.run_selection(test_selection=True)


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
