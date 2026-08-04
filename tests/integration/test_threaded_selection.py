# ABOUTME: Tests a real selection running on a worker thread with the window responsive.
# ABOUTME: Small pool, real library - this is the path a long run takes, just quicker.

import threading

import pytest

from strat_app.qt.csv_tab import CsvTab
from strat_app.qt.log_panel import LogDisplay, LogPanel
from strat_app.qt.workers import QtTaskRunner, QueuedLogView, user_log_handler
from strat_app.sessions.csv_session import CsvSession
from strat_app.sessions.log import GuiLog
from strat_app.sessions.view import LogSection
from strat_app.settings_holder import SettingsHolder
from tests.conftest import ALGORITHM_LINE

PANEL_MIN = 22
TIMEOUT_MS = 120_000


@pytest.fixture
def log_panel(qtbot) -> LogPanel:
    panel = LogPanel()
    qtbot.addWidget(panel)
    return panel


@pytest.fixture
def runner() -> QtTaskRunner:
    return QtTaskRunner()


@pytest.fixture
def tab(qtbot, log_panel: LogPanel, settings_path, runner: QtTaskRunner) -> CsvTab:
    tab = CsvTab()
    qtbot.addWidget(tab)
    display = LogDisplay(
        {
            LogSection.CSV_FEATURES: tab.features_output,
            LogSection.CSV_SELECTION: tab.people_output,
            LogSection.DETAILED_LOG: log_panel.browser,
        }
    )
    tab.session = CsvSession(tab, GuiLog(QueuedLogView(display)), SettingsHolder(settings_path), runner=runner)
    return tab


def test_a_selection_runs_without_blocking_the_gui_thread(
    qtbot, tab: CsvTab, runner: QtTaskRunner, categories_contents: str, people_contents: str
) -> None:
    tab.session.add_feature_content(categories_contents)
    tab.session.add_people_content(people_contents)
    tab.panel_size_spin.setValue(PANEL_MIN)

    with qtbot.waitSignal(runner.finished, timeout=TIMEOUT_MS):
        tab.run_selection()
        # the GUI thread is still ours while the selection is in flight
        assert tab.busy_bar.isVisibleTo(tab)

    assert not tab.busy_bar.isVisibleTo(tab)
    assert tab.save_selected_button.isEnabled()
    assert tab.save_remaining_button.isEnabled()


def test_the_output_is_written_where_asked(
    qtbot, tab: CsvTab, runner: QtTaskRunner, tmp_path, categories_contents: str, people_contents: str
) -> None:
    tab.session.add_feature_content(categories_contents)
    tab.session.add_people_content(people_contents)
    tab.panel_size_spin.setValue(PANEL_MIN)

    with qtbot.waitSignal(runner.finished, timeout=TIMEOUT_MS):
        tab.run_selection()

    selected = tmp_path / "selected.csv"
    tab.write_selected(selected)
    assert len(selected.read_text().strip().splitlines()) == PANEL_MIN + 1


def test_the_library_log_arrives_while_the_selection_runs(
    qtbot, tab: CsvTab, runner: QtTaskRunner, log_panel: LogPanel, categories_contents: str, people_contents: str
) -> None:
    """The lines the library logs as it goes are the only sign of life on a long run."""
    tab.session.add_feature_content(categories_contents)
    tab.session.add_people_content(people_contents)
    tab.panel_size_spin.setValue(PANEL_MIN)

    def receive(line: str) -> None:
        tab.session.gui_log.add(LogSection.DETAILED_LOG, line)

    with user_log_handler(receive), qtbot.waitSignal(runner.finished, timeout=TIMEOUT_MS):
        tab.run_selection()

    qtbot.waitUntil(lambda: ALGORITHM_LINE in log_panel.browser.toPlainText(), timeout=TIMEOUT_MS)


def test_the_report_does_not_repeat_the_lines_already_logged(
    qtbot, tab: CsvTab, runner: QtTaskRunner, log_panel: LogPanel, categories_contents: str, people_contents: str
) -> None:
    tab.session.add_feature_content(categories_contents)
    tab.session.add_people_content(people_contents)
    tab.panel_size_spin.setValue(PANEL_MIN)

    def receive(line: str) -> None:
        tab.session.gui_log.add(LogSection.DETAILED_LOG, line)

    with user_log_handler(receive), qtbot.waitSignal(runner.finished, timeout=TIMEOUT_MS):
        tab.run_selection()

    qtbot.waitUntil(lambda: ALGORITHM_LINE in log_panel.browser.toPlainText(), timeout=TIMEOUT_MS)
    assert log_panel.browser.toPlainText().count(ALGORITHM_LINE) == 1


def test_the_work_itself_leaves_the_gui_thread(
    qtbot, monkeypatch, tab: CsvTab, runner: QtTaskRunner, categories_contents: str, people_contents: str
) -> None:
    tab.session.add_feature_content(categories_contents)
    tab.session.add_people_content(people_contents)
    tab.panel_size_spin.setValue(PANEL_MIN)
    threads: list[threading.Thread] = []
    original = tab.session._stratify  # noqa: SLF001

    def watched(*, test_selection: bool) -> object:
        threads.append(threading.current_thread())
        return original(test_selection=test_selection)

    monkeypatch.setattr(tab.session, "_stratify", watched)

    with qtbot.waitSignal(runner.finished, timeout=TIMEOUT_MS):
        tab.run_selection()

    assert threads and threading.main_thread() not in threads
