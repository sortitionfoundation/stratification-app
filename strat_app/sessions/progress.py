# ABOUTME: Decides which of the library's progress events are worth showing the user.
# ABOUTME: Free of Qt, so the deciding can be tested against a clock a test controls.

import time
from collections.abc import Callable
from typing import NamedTuple

# Ten a second is more than the eye can follow and far fewer than the library emits.
DEFAULT_MIN_INTERVAL_SECONDS = 0.1


class PhaseStart(NamedTuple):
    """A new phase of work, with a total if the library knows one."""

    name: str
    total: int | None
    message: str


class ProgressUpdate(NamedTuple):
    """Progress within the current phase. A total of None means it has no fixed end."""

    current: int
    total: int | None
    message: str


class ProgressThrottle:
    """
    Turns the library's flood of progress events into a trickle worth displaying.

    The library calls `update()` every iteration of its inner loops and says plainly
    that it does not throttle - its docs mention hundreds of calls a second on a fast
    solver. Passing each one on would flood whatever is displaying them.

    Phase changes and the last value of a phase are never dropped. Those are the two
    the user would actually notice missing: a label lagging behind the bar, and a
    determinate bar stopping at 187/200 because the 200 arrived too soon after the 187.
    """

    def __init__(
        self,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._min_interval = min_interval_seconds
        self._now = now
        self._total: int | None = None
        self._in_phase = False
        self._last_sent = 0.0
        self._pending: ProgressUpdate | None = None

    def start_phase(self, name: str, total: int | None, message: str) -> PhaseStart:
        self._total = total
        self._in_phase = True
        self._pending = None
        # not `self._now()` - so the first update of a phase is never held back
        self._last_sent = 0.0
        return PhaseStart(name=name, total=total, message=message)

    def update(self, current: int, message: str) -> ProgressUpdate | None:
        if not self._in_phase:
            return None
        update = ProgressUpdate(current=current, total=self._total, message=message)
        now = self._now()
        if now - self._last_sent < self._min_interval:
            self._pending = update
            return None
        self._last_sent = now
        self._pending = None
        return update

    def end_phase(self) -> ProgressUpdate | None:
        """Flush whatever the throttle was sitting on, so a phase ends where it really got to."""
        pending = self._pending
        self._pending = None
        self._in_phase = False
        return pending
