# ABOUTME: Runs slow work on a QThread and gets the results back on the GUI thread.
# ABOUTME: Also bridges the library's user_logger into the app, so long runs report progress.

import logging
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, Signal

from strat_app.sessions.view import LogEntry, LogSection, LogView

USER_LOGGER_NAME = "sortition_algorithms_user"


class _Task(QObject):
    """One piece of work, living on its own thread."""

    done = Signal(object, object)  # the callback to call, and the result
    failed = Signal(object, object)  # the callback to call, and the error

    def __init__(
        self,
        work: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        super().__init__()
        self._work = work
        self._on_done = on_done
        self._on_error = on_error

    def run(self) -> None:
        try:
            result = self._work()
        except Exception as error:
            self.failed.emit(self._on_error, error)
        else:
            self.done.emit(self._on_done, result)


class QtTaskRunner(QObject):
    """
    A TaskRunner that runs the work on a QThread.

    The callbacks are delivered through this object, which lives on the GUI thread, so
    a queued connection lands them there too - which is what lets them touch widgets.
    """

    finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._threads: list[tuple[QThread, _Task]] = []

    def run(
        self,
        work: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        thread = QThread()
        task = _Task(work, on_done, on_error)
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.done.connect(self._deliver_done, Qt.ConnectionType.QueuedConnection)
        task.failed.connect(self._deliver_failed, Qt.ConnectionType.QueuedConnection)
        task.done.connect(thread.quit)
        task.failed.connect(thread.quit)
        self._threads.append((thread, task))
        thread.start()

    def running(self) -> bool:
        return any(thread.isRunning() for thread, _ in self._threads)

    def wait(self, timeout_ms: int = 30_000) -> None:
        """Let the threads finish - used when shutting down."""
        for thread, _ in self._threads:
            thread.quit()
            thread.wait(timeout_ms)

    def _deliver_done(self, callback: Callable[[Any], None], result: Any) -> None:
        try:
            callback(result)
        finally:
            self._reap()
            self.finished.emit()

    def _deliver_failed(self, callback: Callable[[Exception], None], error: Exception) -> None:
        try:
            callback(error)
        finally:
            self._reap()
            self.finished.emit()

    def _reap(self) -> None:
        self._threads = [pair for pair in self._threads if pair[0].isRunning()]


class QueuedLogView(QObject):
    """
    A LogView that can be called from any thread.

    Log entries are the one thing the session layer produces while work is in flight,
    so they need a safe way across to the widget that shows them.
    """

    _entries = Signal(object, object)

    def __init__(self, view: LogView) -> None:
        super().__init__()
        self._view = view
        self._entries.connect(self._show, Qt.ConnectionType.QueuedConnection)

    def show_log(self, section: LogSection, entries: Sequence[LogEntry]) -> None:
        # a copy, because the session goes on appending to its own list
        self._entries.emit(section, list(entries))

    def _show(self, section: LogSection, entries: Sequence[LogEntry]) -> None:
        self._view.show_log(section, entries)


class UserLogHandler(logging.Handler):
    """
    A logging handler that hands each record to Qt.

    The library logs to `sortition_algorithms_user` as a run progresses - which trial
    it is on, which algorithm it picked. Sending those through a signal is what makes
    the detailed log fill in during a run rather than all at once at the end.
    """

    def __init__(self) -> None:
        super().__init__()
        self._emitter = _LineEmitter()

    def connect(self, receiver: Callable[[str], None]) -> None:
        self._emitter.line.connect(receiver, Qt.ConnectionType.QueuedConnection)

    def emit(self, record: logging.LogRecord) -> None:
        self._emitter.line.emit(self.format(record))


class _LineEmitter(QObject):
    line = Signal(str)


@contextmanager
def user_log_handler(receiver: Callable[[str], None]) -> Generator[UserLogHandler, None, None]:
    """
    Send the library's user-facing log to `receiver` for as long as the block runs.

    The original handlers are put back afterwards, so a second run does not log twice.
    """
    handler = UserLogHandler()
    handler.connect(receiver)
    logger = logging.getLogger(USER_LOGGER_NAME)
    original = logger.handlers[:]
    for old in original:
        logger.removeHandler(old)
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        for old in original:
            logger.addHandler(old)
