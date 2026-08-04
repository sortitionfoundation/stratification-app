# ABOUTME: Tests that both tabs turn the library's progress events into an honest bar.
# ABOUTME: Determinate where the library knows a total, and busy where it does not.

from typing import TYPE_CHECKING, cast

import pytest

from strat_app.qt.csv_tab import CsvTab
from strat_app.qt.gsheet_tab import GSheetTab
from tests.fakes import CallRecorder

if TYPE_CHECKING:
    from strat_app.sessions.csv_session import CsvSession
    from strat_app.sessions.gsheet_session import GSheetSession

# The two tabs deliberately duplicate this code rather than share a widget, so the
# tests run against both to keep the two copies honest about behaving the same.
TABS = ["csv", "gsheet"]


@pytest.fixture(params=TABS)
def tab(request, qtbot) -> CsvTab | GSheetTab:
    if request.param == "csv":
        made: CsvTab | GSheetTab = CsvTab()
        made.session = cast("CsvSession", CallRecorder())
    else:
        made = GSheetTab()
        made.session = cast("GSheetSession", CallRecorder())
    qtbot.addWidget(made)
    return made


def test_the_bar_is_hidden_until_there_is_work(tab: CsvTab | GSheetTab) -> None:
    assert not tab.busy_bar.isVisibleTo(tab)


def test_going_busy_starts_out_indeterminate(tab: CsvTab | GSheetTab) -> None:
    """Nothing is known about the work yet, so all we can honestly show is that it started."""
    tab.set_busy(busy=True)

    assert tab.busy_bar.maximum() == 0
    assert tab.progress_label.text() == ""


def test_a_phase_with_a_total_makes_the_bar_determinate(tab: CsvTab | GSheetTab) -> None:
    tab.set_busy(busy=True)

    tab.start_progress_phase("multiplicative_weights", 200, "Searching for diverse committees")

    assert tab.busy_bar.maximum() == 200
    assert tab.busy_bar.value() == 0
    assert tab.progress_label.text() == "Searching for diverse committees"


def test_a_phase_without_a_total_leaves_the_bar_busy(tab: CsvTab | GSheetTab) -> None:
    """A convergence loop has no fixed end - a percentage would be a lie."""
    tab.set_busy(busy=True)

    tab.start_progress_phase("maximin_optimization", None, "Optimizing maximin distribution")

    assert tab.busy_bar.maximum() == 0
    assert tab.progress_label.text() == "Optimizing maximin distribution"


def test_progress_moves_the_bar_and_the_label(tab: CsvTab | GSheetTab) -> None:
    tab.set_busy(busy=True)
    tab.start_progress_phase("multiplicative_weights", 200, "Searching")

    tab.set_progress(47, 200, "Round 47/200: 31 committees found")

    assert tab.busy_bar.value() == 47
    assert tab.progress_label.text() == "Round 47/200: 31 committees found"


def test_progress_in_an_indeterminate_phase_only_moves_the_label(tab: CsvTab | GSheetTab) -> None:
    tab.set_busy(busy=True)
    tab.start_progress_phase("maximin_optimization", None, "Optimizing")

    tab.set_progress(12, None, "Iteration 12")

    assert tab.busy_bar.maximum() == 0
    assert tab.progress_label.text() == "Iteration 12"


def test_a_second_run_does_not_start_where_the_first_finished(tab: CsvTab | GSheetTab) -> None:
    """Otherwise the bar sits full and the label stale for as long as the new run takes."""
    tab.set_busy(busy=True)
    tab.start_progress_phase("multiplicative_weights", 200, "Searching")
    tab.set_progress(200, 200, "Round 200/200")
    tab.set_busy(busy=False)

    tab.set_busy(busy=True)

    assert tab.busy_bar.maximum() == 0
    assert tab.progress_label.text() == ""


def test_the_label_is_hidden_along_with_the_bar(tab: CsvTab | GSheetTab) -> None:
    tab.set_busy(busy=True)
    assert tab.progress_label.isVisibleTo(tab)

    tab.set_busy(busy=False)

    assert not tab.progress_label.isVisibleTo(tab)
