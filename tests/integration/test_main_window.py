# ABOUTME: Tests for the window that holds the two tabs and the shared detailed log.
# ABOUTME: Also covers routing log sections to the output area each one belongs in.

import pytest

from strat_app.qt.log_panel import LogDisplay, LogPanel
from strat_app.qt.main_window import GSHEET_TAB_INDEX, MainWindow, tab_title
from strat_app.sessions.view import LogSection

CSV_TAB_TITLE = "CSV file input & output"
GSHEET_TAB_TITLE = "Google Sheet input & output"


@pytest.fixture
def window(qtbot, settings_path) -> MainWindow:
    window = MainWindow(settings_path=settings_path)
    qtbot.addWidget(window)
    return window


def test_the_window_has_both_tabs(window: MainWindow) -> None:
    titles = [window.tabs.tabText(index) for index in range(window.tabs.count())]

    assert titles == [tab_title(CSV_TAB_TITLE), tab_title(GSHEET_TAB_TITLE)]


def test_the_ampersand_in_a_tab_title_is_not_read_as_a_shortcut(window: MainWindow) -> None:
    """Unescaped, Qt swallows the ampersand and the tab reads "CSV file input _output"."""
    assert window.tabs.tabText(0) == "CSV file input && output"


def test_the_google_sheet_tab_is_the_one_showing(window: MainWindow) -> None:
    """Same as the old page, which marked the gsheet tab active."""
    assert window.tabs.currentIndex() == GSHEET_TAB_INDEX


def test_the_detailed_log_starts_open(window: MainWindow) -> None:
    assert window.log_panel.isChecked()


def test_the_detailed_log_can_be_collapsed(window: MainWindow) -> None:
    window.log_panel.setChecked(False)

    assert not window.log_panel.browser.isVisibleTo(window.log_panel)


def test_each_tab_has_a_session_that_can_talk_back_to_it(window: MainWindow) -> None:
    assert window.csv_tab.session.view is window.csv_tab
    assert window.gsheet_tab.session.view is window.gsheet_tab


def test_both_tabs_share_one_settings_holder(window: MainWindow) -> None:
    """Otherwise a broken settings file gets reported twice, once per tab."""
    assert window.csv_tab.session.settings_holder is window.gsheet_tab.session.settings_holder


@pytest.mark.parametrize(
    ("section", "attribute"),
    [
        (LogSection.CSV_FEATURES, "csv_features"),
        (LogSection.CSV_SELECTION, "csv_selection"),
        (LogSection.GSHEET_FEATURES, "gsheet_features"),
        (LogSection.GSHEET_SELECTION, "gsheet_selection"),
        (LogSection.DETAILED_LOG, "detailed_log"),
    ],
)
def test_each_log_section_reaches_its_own_output_area(
    qtbot, window: MainWindow, section: LogSection, attribute: str
) -> None:
    areas = {
        "csv_features": window.csv_tab.features_output,
        "csv_selection": window.csv_tab.people_output,
        "gsheet_features": window.gsheet_tab.features_output,
        "gsheet_selection": window.gsheet_tab.people_output,
        "detailed_log": window.log_panel.browser,
    }

    window.gui_log.reset(section, "a message for this section")

    # delivery is queued, since worker threads write to the log too
    qtbot.waitUntil(lambda: "a message for this section" in areas[attribute].toPlainText(), timeout=5000)
    for name, area in areas.items():
        if name != attribute:
            assert "a message for this section" not in area.toPlainText()


def test_the_log_display_complains_about_an_unrouted_section(qtbot) -> None:
    panel = LogPanel()
    qtbot.addWidget(panel)
    display = LogDisplay({LogSection.DETAILED_LOG: panel.browser})

    with pytest.raises(KeyError):
        display.show_log(LogSection.CSV_FEATURES, ["nowhere to put this"])
