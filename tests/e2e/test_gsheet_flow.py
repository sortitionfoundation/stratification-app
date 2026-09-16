# ABOUTME: End to end test of the Google Sheet tab against a fake spreadsheet.
# ABOUTME: Proves the tab, the worker and the wiring - it does not prove gspread itself.

from typing import TYPE_CHECKING, cast

import pytest

from strat_app.qt.main_window import GSHEET_TAB_INDEX, MainWindow
from strat_app.sessions.gsheet_session import GSheetSession
from strat_app.settings_holder import SettingsHolder
from tests.fakes import FakeGSheetDataSource

if TYPE_CHECKING:
    from sortition_algorithms import adapters

PANEL_MIN = 22
PANEL_MAX = 24
SHEET_NAME = "My Assembly"
TIMEOUT_MS = 120_000


@pytest.fixture
def data_source(categories_contents: str, people_contents: str) -> FakeGSheetDataSource:
    return FakeGSheetDataSource(
        tabs={"Categories": categories_contents, "Respondents": people_contents},
        sheet_names=[SHEET_NAME],
    )


@pytest.fixture
def window(qtbot, settings_path, data_source: FakeGSheetDataSource) -> MainWindow:
    window = MainWindow(settings_path=settings_path)
    qtbot.addWidget(window)
    window.tabs.setCurrentIndex(GSHEET_TAB_INDEX)
    # the only substitution in the whole flow: a spreadsheet we do not need credentials for
    window.gsheet_tab.session = GSheetSession(
        window.gsheet_tab,
        window.gui_log,
        SettingsHolder(settings_path),
        data_source=cast("adapters.GSheetDataSource", data_source),
        runner=window.task_runner,
    )
    return window


def test_the_whole_g_sheet_flow(qtbot, window: MainWindow, data_source: FakeGSheetDataSource) -> None:
    tab = window.gsheet_tab

    # step 1 - name the spreadsheet
    qtbot.keyClicks(tab.sheet_name_edit, SHEET_NAME)
    assert tab.load_button.isEnabled()

    # step 2 - load it
    with qtbot.waitSignal(window.task_runner.finished, timeout=TIMEOUT_MS):
        tab.load_g_sheet()

    qtbot.waitUntil(lambda: "Number of features found: 4" in tab.features_output.toPlainText(), timeout=TIMEOUT_MS)
    qtbot.waitUntil(
        lambda: "Successfully loaded features and people." in tab.people_output.toPlainText(), timeout=TIMEOUT_MS
    )
    assert (tab.panel_size_spin.minimum(), tab.panel_size_spin.maximum()) == (PANEL_MIN, PANEL_MAX)

    # step 3 - the panel size, and running. The write is a second trip to the runner.
    tab.panel_size_spin.setValue(PANEL_MIN)
    assert tab.run_button.isEnabled()

    with qtbot.waitSignal(window.task_runner.finished, timeout=TIMEOUT_MS):
        tab.run_selection()
    with qtbot.waitSignal(window.task_runner.finished, timeout=TIMEOUT_MS):
        pass

    qtbot.waitUntil(lambda: "Selection process finished." in window.log_panel.browser.toPlainText(), timeout=TIMEOUT_MS)
    written = data_source.selected_file.getvalue().strip().splitlines()
    assert len(written) == PANEL_MIN + 1
    assert not tab.busy_bar.isVisibleTo(tab)


def test_a_missing_tab_is_reported_and_leaves_the_tab_usable(qtbot, window: MainWindow) -> None:
    tab = window.gsheet_tab
    qtbot.keyClicks(tab.sheet_name_edit, SHEET_NAME)
    tab.features_tab_edit.setText("Not A Tab")

    with qtbot.waitSignal(window.task_runner.finished, timeout=TIMEOUT_MS):
        tab.load_g_sheet()

    # wait for the last line, since each update reaches the widget on its own event loop turn
    qtbot.waitUntil(
        lambda: "Fix the problems and try loading again." in tab.features_output.toPlainText(), timeout=TIMEOUT_MS
    )
    assert "no tab called 'Not A Tab'" in tab.features_output.toPlainText()
    assert not tab.busy_bar.isVisibleTo(tab)
    assert tab.load_button.isEnabled()
    assert not tab.run_button.isEnabled()


def test_asking_for_two_selections_warns_and_skips_the_remaining_tab(
    qtbot, window: MainWindow, data_source: FakeGSheetDataSource
) -> None:
    tab = window.gsheet_tab
    qtbot.keyClicks(tab.sheet_name_edit, SHEET_NAME)
    tab.number_selections_spin.setValue(2)

    with qtbot.waitSignal(window.task_runner.finished, timeout=TIMEOUT_MS):
        tab.load_g_sheet()

    qtbot.waitUntil(lambda: "You've asked for 2 selections" in tab.people_output.toPlainText(), timeout=TIMEOUT_MS)
    assert tab.session._safe_gen_rem_tab() is False  # noqa: SLF001
