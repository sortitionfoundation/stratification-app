# ABOUTME: Carries the library's progress events from the worker thread to the GUI thread.
# ABOUTME: Satisfies sortition_algorithms' ProgressReporter protocol; the throttling is elsewhere.

from PySide6.QtCore import QObject, Qt, Signal

from strat_app.sessions.progress import ProgressThrottle


class QtProgressReporter(QObject):
    """
    A ProgressReporter that turns the library's events into Qt signals.

    The library calls this from wherever the selection is running, which for us is a
    QThread. The signals are emitted with a queued connection, so the slots run on the
    GUI thread and may touch widgets.

    Everything is emitted through a ProgressThrottle, because the library states it
    does not throttle and calls update() every iteration of its inner loops.
    """

    phase_started = Signal(str, object, str)  # name, total or None, message
    progressed = Signal(int, object, str)  # current, total or None, message

    def __init__(self, throttle: ProgressThrottle | None = None) -> None:
        super().__init__()
        self._throttle = throttle or ProgressThrottle()

    def connect_phase_started(self, receiver: object) -> None:
        self.phase_started.connect(receiver, Qt.ConnectionType.QueuedConnection)

    def connect_progressed(self, receiver: object) -> None:
        self.progressed.connect(receiver, Qt.ConnectionType.QueuedConnection)

    def start_phase(self, name: str, total: int | None = None, *, message: str | None = None) -> None:
        phase = self._throttle.start_phase(name, total, message or "")
        self.phase_started.emit(phase.name, phase.total, phase.message)

    def update(self, current: int, *, message: str | None = None) -> None:
        update = self._throttle.update(current, message or "")
        if update is not None:
            self.progressed.emit(update.current, update.total, update.message)

    def end_phase(self) -> None:
        update = self._throttle.end_phase()
        if update is not None:
            self.progressed.emit(update.current, update.total, update.message)
