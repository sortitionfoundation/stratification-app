# ABOUTME: Tests for the Google Sheet tab widget - that it obeys GSheetView and drives the session.
# ABOUTME: No spreadsheet is touched; the session is a recorder.

from typing import TYPE_CHECKING, cast

import pytest
from PySide6.QtCore import Qt

from strat_app.qt.gsheet_tab import GSheetTab
from tests.fakes import CallRecorder

if TYPE_CHECKING:
    from strat_app.sessions.gsheet_session import GSheetSession
    from strat_app.sessions.view import GSheetView

PANEL_MIN = 22
PANEL_MAX = 24


@pytest.fixture
def session() -> CallRecorder:
    return CallRecorder()


@pytest.fixture
def tab(qtbot, session: CallRecorder) -> GSheetTab:
    tab = GSheetTab()
    tab.session = cast("GSheetSession", session)
    qtbot.addWidget(tab)
    return tab


####################################
# the tab as a view for the session
####################################


def test_starts_with_loading_and_running_disabled(tab: GSheetTab) -> None:
    assert not tab.load_button.isEnabled()
    assert not tab.run_button.isEnabled()
    assert not tab.run_test_button.isEnabled()


def test_the_two_run_buttons_are_controlled_separately(tab: GSheetTab) -> None:
    """A test panel is refused for several selections, so it needs its own switch."""
    tab.set_run_enabled(enabled=True)
    tab.set_test_run_enabled(enabled=False)

    assert tab.run_button.isEnabled()
    assert not tab.run_test_button.isEnabled()


def test_going_busy_disables_both_run_buttons_and_restores_them(tab: GSheetTab) -> None:
    tab.set_run_enabled(enabled=True)
    tab.set_test_run_enabled(enabled=True)

    tab.set_busy(busy=True)

    assert not tab.run_button.isEnabled()
    assert not tab.run_test_button.isEnabled()

    tab.set_busy(busy=False)

    assert tab.run_button.isEnabled()
    assert tab.run_test_button.isEnabled()


def test_a_test_panel_refused_before_a_run_stays_refused_after_it(tab: GSheetTab) -> None:
    """Going busy must not hand back a button that was deliberately disabled."""
    tab.set_run_enabled(enabled=True)
    tab.set_test_run_enabled(enabled=False)

    tab.set_busy(busy=True)
    tab.set_busy(busy=False)

    assert tab.run_button.isEnabled()
    assert not tab.run_test_button.isEnabled()


def test_the_advanced_settings_start_hidden_with_the_current_defaults(tab: GSheetTab) -> None:
    assert not tab.advanced_settings.isChecked()
    assert tab.features_tab_edit.text() == "Categories"
    assert tab.people_tab_edit.text() == "Respondents"
    assert tab.gen_rem_tab_check.isChecked()
    assert tab.number_selections_spin.value() == 1


def test_opening_the_advanced_settings_shows_them(tab: GSheetTab) -> None:
    assert not tab.advanced_contents.isVisibleTo(tab.advanced_settings)

    tab.advanced_settings.setChecked(True)

    assert tab.advanced_contents.isVisibleTo(tab.advanced_settings)


def test_the_number_of_selections_cannot_go_below_one(tab: GSheetTab) -> None:
    tab.number_selections_spin.setValue(0)

    assert tab.number_selections_spin.value() == 1


def test_enabling_the_load_button(tab: GSheetTab) -> None:
    tab.set_load_enabled(enabled=True)

    assert tab.load_button.isEnabled()


def test_setting_the_panel_size_range_bounds_the_spin_box(tab: GSheetTab) -> None:
    tab.set_panel_size_range(PANEL_MIN, PANEL_MAX)

    assert tab.panel_size_spin.minimum() == PANEL_MIN
    assert tab.panel_size_spin.maximum() == PANEL_MAX
    assert f"({PANEL_MIN}-{PANEL_MAX})" in tab.panel_size_label.text()


def test_clearing_the_range_puts_the_label_back(tab: GSheetTab) -> None:
    tab.set_panel_size_range(PANEL_MIN, PANEL_MAX)

    tab.set_panel_size_range(0, 0)

    assert "(" not in tab.panel_size_label.text()
    assert tab.panel_size_spin.value() == 0


def test_enabling_and_disabling_the_run_buttons(tab: GSheetTab) -> None:
    tab.set_run_enabled(enabled=True)
    tab.set_test_run_enabled(enabled=True)
    assert tab.run_button.isEnabled()
    assert tab.run_test_button.isEnabled()

    tab.set_run_enabled(enabled=False)
    tab.set_test_run_enabled(enabled=False)
    assert not tab.run_button.isEnabled()
    assert not tab.run_test_button.isEnabled()


#######################################
# user actions reaching the session
#######################################


def test_typing_a_sheet_name_tells_the_session(qtbot, tab: GSheetTab, session: CallRecorder) -> None:
    qtbot.keyClicks(tab.sheet_name_edit, "My Assembly")

    assert session.last_args("update_g_sheet_name") == ("My Assembly",)


def test_clicking_load_loads_the_sheet(qtbot, tab: GSheetTab, session: CallRecorder) -> None:
    tab.set_load_enabled(enabled=True)

    qtbot.mouseClick(tab.load_button, Qt.MouseButton.LeftButton)

    assert session.called("load_g_sheet")


def test_editing_the_categories_tab_name_tells_the_session(tab: GSheetTab, session: CallRecorder) -> None:
    tab.features_tab_edit.setText("Other Categories")

    assert session.last_args("update_features_tab_name") == ("Other Categories",)


def test_editing_the_respondents_tab_name_tells_the_session(tab: GSheetTab, session: CallRecorder) -> None:
    tab.people_tab_edit.setText("Other Respondents")

    assert session.last_args("update_people_tab_name") == ("Other Respondents",)


def test_unchecking_the_remaining_tab_tells_the_session(tab: GSheetTab, session: CallRecorder) -> None:
    tab.gen_rem_tab_check.setChecked(False)

    assert session.last_args("update_gen_rem_tab") == (False,)


def test_changing_the_number_of_selections_tells_the_session(tab: GSheetTab, session: CallRecorder) -> None:
    tab.number_selections_spin.setValue(3)

    assert session.last_args("set_number_selections") == (3,)


def test_changing_the_spin_box_tells_the_session(tab: GSheetTab, session: CallRecorder) -> None:
    tab.set_panel_size_range(PANEL_MIN, PANEL_MAX)

    tab.panel_size_spin.setValue(PANEL_MAX)

    assert session.last_args("set_panel_size") == (PANEL_MAX,)


def test_clicking_run_starts_a_real_selection(qtbot, tab: GSheetTab, session: CallRecorder) -> None:
    tab.set_run_enabled(enabled=True)

    qtbot.mouseClick(tab.run_button, Qt.MouseButton.LeftButton)

    assert session.last_args("run_selection") == (False,)


def test_clicking_the_test_panel_button_asks_for_a_test_selection(qtbot, tab: GSheetTab, session: CallRecorder) -> None:
    tab.set_test_run_enabled(enabled=True)

    qtbot.mouseClick(tab.run_test_button, Qt.MouseButton.LeftButton)

    assert session.last_args("run_selection") == (True,)


def test_the_tab_satisfies_the_view_protocol(tab: GSheetTab) -> None:
    """The annotation is the test - mypy checks the widget against the protocol."""
    view: GSheetView = tab

    assert view is tab


###################
# the busy indicator
###################


def test_the_busy_indicator_starts_hidden(tab: GSheetTab) -> None:
    assert not tab.busy_bar.isVisibleTo(tab)


def test_the_busy_indicator_shows_while_work_is_in_flight(tab: GSheetTab) -> None:
    tab.set_busy(busy=True)

    assert tab.busy_bar.isVisibleTo(tab)


def test_loading_is_refused_while_already_loading(tab: GSheetTab) -> None:
    tab.set_load_enabled(enabled=True)

    tab.set_busy(busy=True)

    assert not tab.load_button.isEnabled()
    assert not tab.run_button.isEnabled()


def test_the_buttons_come_back_when_the_work_finishes(tab: GSheetTab) -> None:
    tab.set_load_enabled(enabled=True)
    tab.set_run_enabled(enabled=True)
    tab.set_busy(busy=True)

    tab.set_busy(busy=False)

    assert tab.load_button.isEnabled()
    assert tab.run_button.isEnabled()
