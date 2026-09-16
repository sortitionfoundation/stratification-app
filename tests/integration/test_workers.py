# ABOUTME: Tests for running work off the GUI thread and getting the results back safely.
# ABOUTME: A frozen window looks like a crash, and a widget touched off-thread is a real crash.

import logging
import threading
from collections.abc import Callable
from typing import Any

import pytest
from PySide6.QtCore import QThread

from strat_app.qt.workers import QtTaskRunner, QueuedLogView, UserLogHandler, user_log_handler
from strat_app.sessions.view import LogSection

TIMEOUT_MS = 10_000


@pytest.fixture
def runner(qtbot) -> QtTaskRunner:
    return QtTaskRunner()


def test_the_work_happens_off_the_gui_thread(qtbot, runner: QtTaskRunner) -> None:
    where_the_work_ran = {}

    def work() -> str:
        where_the_work_ran["thread"] = threading.current_thread()
        return "done"

    with qtbot.waitSignal(runner.finished, timeout=TIMEOUT_MS):
        runner.run(work, lambda result: None, lambda error: None)

    assert where_the_work_ran["thread"] is not threading.main_thread()


def test_the_result_comes_back_on_the_gui_thread(qtbot, runner: QtTaskRunner) -> None:
    """Anything touching a widget runs here, so it had better be the GUI thread."""
    seen: dict[str, Any] = {}

    def on_done(result: str) -> None:
        seen["result"] = result
        seen["thread"] = threading.current_thread()

    with qtbot.waitSignal(runner.finished, timeout=TIMEOUT_MS):
        runner.run(lambda: "the answer", on_done, lambda error: None)

    assert seen["result"] == "the answer"
    assert seen["thread"] is threading.main_thread()


def test_an_exception_reaches_the_error_callback_on_the_gui_thread(qtbot, runner: QtTaskRunner) -> None:
    seen: dict[str, Any] = {}

    def explode() -> None:
        msg = "it went wrong"
        raise RuntimeError(msg)

    def on_error(error: Exception) -> None:
        seen["error"] = error
        seen["thread"] = threading.current_thread()

    with qtbot.waitSignal(runner.finished, timeout=TIMEOUT_MS):
        runner.run(explode, lambda result: None, on_error)

    assert str(seen["error"]) == "it went wrong"
    assert seen["thread"] is threading.main_thread()


def test_the_thread_is_cleaned_up_afterwards(qtbot, runner: QtTaskRunner) -> None:
    with qtbot.waitSignal(runner.finished, timeout=TIMEOUT_MS):
        runner.run(lambda: None, lambda result: None, lambda error: None)

    qtbot.waitUntil(lambda: not runner.running(), timeout=TIMEOUT_MS)


def test_several_tasks_in_a_row(qtbot, runner: QtTaskRunner) -> None:
    results: list[int] = []

    for number in range(3):
        with qtbot.waitSignal(runner.finished, timeout=TIMEOUT_MS):
            runner.run(_doubler(number), results.append, lambda error: None)

    assert results == [0, 2, 4]


#############################
# the live log from the library
#############################


def test_a_log_record_from_a_worker_thread_reaches_the_view(qtbot, runner: QtTaskRunner) -> None:
    """This is what makes the detailed log fill in while a long selection runs."""
    shown: list[str] = []
    handler = UserLogHandler()
    handler.connect(shown.append)

    with qtbot.waitSignal(runner.finished, timeout=TIMEOUT_MS):
        runner.run(lambda: handler.handle(_record("a message from the solver")), lambda r: None, lambda e: None)

    qtbot.waitUntil(lambda: "a message from the solver" in shown, timeout=TIMEOUT_MS)


def test_the_handler_can_be_installed_over_the_library_logger(qtbot) -> None:
    user_logger = logging.getLogger("sortition_algorithms_user")
    original = user_logger.handlers[:]
    lines: list[str] = []

    with user_log_handler(lines.append):
        user_logger.info("during the run")
        # delivery is queued, so it lands on the next turn of the event loop
        qtbot.waitUntil(lambda: lines == ["during the run"], timeout=TIMEOUT_MS)

    user_logger.info("after the run")

    assert lines == ["during the run"]
    assert user_logger.handlers == original


def test_the_queued_log_view_passes_entries_through(qtbot) -> None:
    seen: dict[LogSection, list[str]] = {}

    class Sink:
        def show_log(self, section: LogSection, entries) -> None:
            seen[section] = [str(entry) for entry in entries]

    view = QueuedLogView(Sink())

    view.show_log(LogSection.DETAILED_LOG, ["hello"])

    qtbot.waitUntil(lambda: seen.get(LogSection.DETAILED_LOG) == ["hello"], timeout=TIMEOUT_MS)


def test_the_queued_log_view_delivers_from_a_worker_thread(qtbot, runner: QtTaskRunner) -> None:
    seen: dict[LogSection, list[str]] = {}
    threads: list[threading.Thread] = []

    class Sink:
        def show_log(self, section: LogSection, entries) -> None:
            seen[section] = [str(entry) for entry in entries]
            threads.append(threading.current_thread())

    view = QueuedLogView(Sink())

    with qtbot.waitSignal(runner.finished, timeout=TIMEOUT_MS):
        runner.run(lambda: view.show_log(LogSection.CSV_FEATURES, ["from the worker"]), lambda r: None, lambda e: None)

    qtbot.waitUntil(lambda: seen.get(LogSection.CSV_FEATURES) == ["from the worker"], timeout=TIMEOUT_MS)
    assert threads == [threading.main_thread()]


def _doubler(number: int) -> Callable[[], int]:
    return lambda: number * 2


def _record(message: str) -> logging.LogRecord:
    return logging.LogRecord("sortition_algorithms_user", logging.INFO, __file__, 1, message, None, None)


def test_qthread_is_importable() -> None:
    """Guards against the worker module quietly dropping its Qt import."""
    assert QThread is not None
