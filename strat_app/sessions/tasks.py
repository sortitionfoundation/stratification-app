# ABOUTME: How the session layer runs slow work without knowing anything about threads.
# ABOUTME: Tests use the synchronous runner; the app supplies a Qt one that uses a QThread.

from collections.abc import Callable
from typing import Any, Protocol


class TaskRunner(Protocol):
    """
    Runs a piece of slow work, then calls back with the result or the error.

    Whoever supplies the runner decides where the work happens. The one rule an
    implementation must keep is that the callbacks happen where the session lives -
    for the Qt app, the GUI thread - because they touch the session and its view.
    """

    def run(
        self,
        work: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> None: ...


class SynchronousRunner:
    """Runs the work there and then. No threads, so tests stay predictable."""

    def run(
        self,
        work: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        try:
            result = work()
        except Exception as error:
            on_error(error)
        else:
            on_done(result)
