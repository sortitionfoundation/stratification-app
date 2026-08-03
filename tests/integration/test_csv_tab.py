# ABOUTME: Tests for the CSV tab widget - that it obeys CsvView and drives the session.
# ABOUTME: File dialogs are never opened; the tests call the methods the dialogs would.

from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from PySide6.QtCore import Qt

from strat_app.qt.csv_tab import CsvTab
from tests.conftest import CATEGORIES_CSV, PEOPLE_CSV
from tests.fakes import CallRecorder

if TYPE_CHECKING:
    from strat_app.sessions.csv_session import CsvSession
    from strat_app.sessions.view import CsvView

PANEL_MIN = 22
PANEL_MAX = 24


@pytest.fixture
def session() -> CallRecorder:
    return CallRecorder()


@pytest.fixture
def tab(qtbot, session: CallRecorder) -> CsvTab:
    tab = CsvTab()
    tab.session = cast("CsvSession", session)
    qtbot.addWidget(tab)
    return tab


####################################
# the tab as a view for the session
####################################


def test_starts_with_people_input_and_running_disabled(tab: CsvTab) -> None:
    assert not tab.people_button.isEnabled()
    assert not tab.run_button.isEnabled()
    assert not tab.run_test_button.isEnabled()
    assert not tab.save_selected_button.isEnabled()
    assert not tab.save_remaining_button.isEnabled()


def test_the_categories_button_is_available_from_the_start(tab: CsvTab) -> None:
    assert tab.features_button.isEnabled()


def test_enabling_the_people_input(tab: CsvTab) -> None:
    tab.set_people_input_enabled(enabled=True)

    assert tab.people_button.isEnabled()


def test_setting_the_panel_size_range_bounds_the_spin_box(tab: CsvTab) -> None:
    tab.set_panel_size_range(PANEL_MIN, PANEL_MAX)

    assert tab.panel_size_spin.minimum() == PANEL_MIN
    assert tab.panel_size_spin.maximum() == PANEL_MAX


def test_the_panel_size_range_is_shown_in_the_label(tab: CsvTab) -> None:
    tab.set_panel_size_range(PANEL_MIN, PANEL_MAX)

    assert f"({PANEL_MIN}-{PANEL_MAX})" in tab.panel_size_label.text()


def test_a_size_outside_the_range_cannot_be_set(tab: CsvTab) -> None:
    """The point of the spin box - the old text box let you type anything at all."""
    tab.set_panel_size_range(PANEL_MIN, PANEL_MAX)

    tab.panel_size_spin.setValue(PANEL_MAX + 10)

    assert tab.panel_size_spin.value() == PANEL_MAX


def test_setting_the_panel_size(tab: CsvTab) -> None:
    tab.set_panel_size_range(PANEL_MIN, PANEL_MAX)

    tab.set_panel_size(PANEL_MIN + 1)

    assert tab.panel_size_spin.value() == PANEL_MIN + 1


def test_enabling_and_disabling_the_run_buttons(tab: CsvTab) -> None:
    tab.set_run_enabled(enabled=True)
    assert tab.run_button.isEnabled()
    assert tab.run_test_button.isEnabled()

    tab.set_run_enabled(enabled=False)
    assert not tab.run_button.isEnabled()
    assert not tab.run_test_button.isEnabled()


def test_offering_the_output_enables_saving_it(tab: CsvTab) -> None:
    tab.offer_selected("id,name\n1,Alice\n", "selected.csv")
    tab.offer_remaining("id,name\n2,Bob\n", "remaining.csv")

    assert tab.save_selected_button.isEnabled()
    assert tab.save_remaining_button.isEnabled()


def test_saving_writes_what_was_offered(tab: CsvTab, tmp_path: Path) -> None:
    tab.offer_selected("id,name\n1,Alice\n", "selected.csv")
    target = tmp_path / "chosen-name.csv"

    tab.write_selected(target)

    assert target.read_text() == "id,name\n1,Alice\n"


def test_saving_the_remaining_writes_what_was_offered(tab: CsvTab, tmp_path: Path) -> None:
    tab.offer_remaining("id,name\n2,Bob\n", "remaining.csv")
    target = tmp_path / "left-over.csv"

    tab.write_remaining(target)

    assert target.read_text() == "id,name\n2,Bob\n"


#######################################
# user actions reaching the session
#######################################


def test_choosing_a_categories_file_hands_the_contents_to_the_session(
    tab: CsvTab, session: CallRecorder, categories_contents: str
) -> None:
    tab.load_features_file(CATEGORIES_CSV)

    assert session.last_args("add_feature_content") == (categories_contents,)


def test_the_chosen_categories_file_is_shown(tab: CsvTab) -> None:
    tab.load_features_file(CATEGORIES_CSV)

    assert CATEGORIES_CSV.name in tab.features_label.text()


def test_choosing_a_people_file_hands_the_contents_to_the_session(
    tab: CsvTab, session: CallRecorder, people_contents: str
) -> None:
    tab.load_people_file(PEOPLE_CSV)

    assert session.last_args("add_people_content") == (people_contents,)


def test_changing_the_spin_box_tells_the_session(tab: CsvTab, session: CallRecorder) -> None:
    tab.set_panel_size_range(PANEL_MIN, PANEL_MAX)

    tab.panel_size_spin.setValue(PANEL_MAX)

    assert session.last_args("set_panel_size") == (PANEL_MAX,)


def test_clicking_run_starts_a_real_selection(qtbot, tab: CsvTab, session: CallRecorder) -> None:
    tab.set_run_enabled(enabled=True)

    qtbot.mouseClick(tab.run_button, Qt.MouseButton.LeftButton)

    assert session.last_args("run_selection") == (False,)


def test_clicking_the_test_panel_button_asks_for_a_test_selection(qtbot, tab: CsvTab, session: CallRecorder) -> None:
    tab.set_run_enabled(enabled=True)

    qtbot.mouseClick(tab.run_test_button, Qt.MouseButton.LeftButton)

    assert session.last_args("run_selection") == (True,)


def test_the_tab_satisfies_the_view_protocol(tab: CsvTab) -> None:
    """The annotation is the test - mypy checks the widget against the protocol."""
    view: CsvView = tab

    assert view is tab
