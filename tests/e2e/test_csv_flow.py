# ABOUTME: End to end test of the CSV flow - real window, real library, real files on disk.
# ABOUTME: Everything except the file dialogs, which are driven through the seam behind them.

import csv

import pytest

from strat_app.qt.main_window import CSV_TAB_INDEX, MainWindow
from strat_app.qt.workers import user_log_handler
from tests.conftest import ALGORITHM_LINE, CATEGORIES_CSV, PEOPLE_CSV, PEOPLE_TOO_FEW_CSV

PANEL_MIN = 22
PANEL_MAX = 24
PEOPLE_COUNT = 200
TIMEOUT_MS = 120_000


@pytest.fixture
def window(qtbot, settings_path) -> MainWindow:
    window = MainWindow(settings_path=settings_path)
    qtbot.addWidget(window)
    window.tabs.setCurrentIndex(CSV_TAB_INDEX)
    return window


def ids_from(path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return {row["nationbuilder_id"] for row in csv.DictReader(csv_file)}


def test_the_whole_csv_flow(qtbot, window: MainWindow, tmp_path) -> None:
    tab = window.csv_tab

    # step 1 - the categories
    tab.load_features_file(CATEGORIES_CSV)
    qtbot.waitUntil(lambda: "Number of features found: 4" in tab.features_output.toPlainText(), timeout=TIMEOUT_MS)
    assert tab.people_button.isEnabled()
    assert (tab.panel_size_spin.minimum(), tab.panel_size_spin.maximum()) == (PANEL_MIN, PANEL_MAX)

    # step 2 - the people
    tab.load_people_file(PEOPLE_CSV)
    qtbot.waitUntil(lambda: f"Loaded {PEOPLE_COUNT} people." in tab.people_output.toPlainText(), timeout=TIMEOUT_MS)

    # step 3 - the panel size, and running
    tab.panel_size_spin.setValue(PANEL_MIN)
    assert tab.run_button.isEnabled()

    with qtbot.waitSignal(window.task_runner.finished, timeout=TIMEOUT_MS):
        tab.run_selection()

    # step 4 - the output
    assert tab.save_selected_button.isEnabled()
    selected = tmp_path / "selected.csv"
    remaining = tmp_path / "remaining.csv"
    tab.write_selected(selected)
    tab.write_remaining(remaining)

    selected_ids = ids_from(selected)
    remaining_ids = ids_from(remaining)
    pool_ids = ids_from(PEOPLE_CSV)
    assert len(selected_ids) == PANEL_MIN
    assert selected_ids <= pool_ids
    assert selected_ids | remaining_ids == pool_ids
    assert not selected_ids & remaining_ids


def test_a_test_panel_can_be_produced(qtbot, window: MainWindow, tmp_path) -> None:
    tab = window.csv_tab
    tab.load_features_file(CATEGORIES_CSV)
    tab.load_people_file(PEOPLE_CSV)
    tab.panel_size_spin.setValue(PANEL_MIN)

    with qtbot.waitSignal(window.task_runner.finished, timeout=TIMEOUT_MS):
        tab.run_test_selection()

    selected = tmp_path / "selected.csv"
    tab.write_selected(selected)
    assert len(ids_from(selected)) == PANEL_MIN


def test_the_detailed_log_fills_in_as_the_run_goes(qtbot, window: MainWindow) -> None:
    tab = window.csv_tab
    tab.load_features_file(CATEGORIES_CSV)
    tab.load_people_file(PEOPLE_CSV)
    tab.panel_size_spin.setValue(PANEL_MIN)

    with (
        user_log_handler(window.append_detailed_log),
        qtbot.waitSignal(window.task_runner.finished, timeout=TIMEOUT_MS),
    ):
        tab.run_selection()

    qtbot.waitUntil(lambda: ALGORITHM_LINE in window.log_panel.browser.toPlainText(), timeout=TIMEOUT_MS)
    assert "Selecting... please wait..." in window.log_panel.browser.toPlainText()


def test_the_progress_bar_becomes_determinate_during_a_real_run(qtbot, window: MainWindow) -> None:
    """
    A real maximin run starts with multiplicative_weights, which reports a total.

    This is the whole point of the bump: the bar can say how far through it is rather
    than only that something is happening. Recording the maxima as they arrive rather
    than checking at the end, because the bar goes back to indeterminate for the
    convergence loop that follows.
    """
    tab = window.csv_tab
    tab.load_features_file(CATEGORIES_CSV)
    tab.load_people_file(PEOPLE_CSV)
    tab.panel_size_spin.setValue(PANEL_MIN)
    maxima: list[int] = []
    window.csv_progress.connect_phase_started(lambda name, total, message: maxima.append(tab.busy_bar.maximum()))

    with qtbot.waitSignal(window.task_runner.finished, timeout=TIMEOUT_MS):
        tab.run_selection()
    qtbot.waitUntil(lambda: bool(maxima), timeout=TIMEOUT_MS)

    assert max(maxima) > 0


def test_running_twice_leaves_only_the_second_panel(qtbot, window: MainWindow, tmp_path) -> None:
    """The old app appended one run's output to the last one's."""
    tab = window.csv_tab
    tab.load_features_file(CATEGORIES_CSV)
    tab.load_people_file(PEOPLE_CSV)
    tab.panel_size_spin.setValue(PANEL_MIN)

    for _ in range(2):
        with qtbot.waitSignal(window.task_runner.finished, timeout=TIMEOUT_MS):
            tab.run_selection()

    selected = tmp_path / "selected.csv"
    tab.write_selected(selected)
    assert len(ids_from(selected)) == PANEL_MIN


def test_an_impossible_panel_size_says_so(qtbot, window: MainWindow) -> None:
    tab = window.csv_tab
    tab.load_features_file(CATEGORIES_CSV)
    # a pool of five people cannot fill a panel of twenty two
    tab.load_people_file(PEOPLE_TOO_FEW_CSV)
    tab.panel_size_spin.setValue(PANEL_MIN)

    with qtbot.waitSignal(window.task_runner.finished, timeout=TIMEOUT_MS):
        tab.run_selection()

    qtbot.waitUntil(
        lambda: "No panels written to CSV, process ended." in window.log_panel.browser.toPlainText(),
        timeout=TIMEOUT_MS,
    )
    assert not tab.save_selected_button.isEnabled()
    # and the app is still usable afterwards
    assert not window.csv_tab.busy_bar.isVisibleTo(window.csv_tab)
