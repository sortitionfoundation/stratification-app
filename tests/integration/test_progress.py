# ABOUTME: Tests the bridge carrying the library's progress events over to the GUI thread.
# ABOUTME: The library calls the reporter from a worker thread, so the crossing has to be safe.

import threading

import pytest
from sortition_algorithms.progress import ProgressReporter

from strat_app.qt.progress import QtProgressReporter
from strat_app.qt.workers import QtTaskRunner

TIMEOUT_MS = 10_000


@pytest.fixture
def reporter(qtbot) -> QtProgressReporter:
    return QtProgressReporter()


def test_it_satisfies_the_library_protocol(reporter: QtProgressReporter) -> None:
    """The library checks against this protocol at runtime, so a missing method is fatal."""
    assert isinstance(reporter, ProgressReporter)


def test_a_phase_start_carries_its_name_total_and_message(qtbot, reporter: QtProgressReporter) -> None:
    with qtbot.waitSignal(reporter.phase_started, timeout=TIMEOUT_MS) as blocker:
        reporter.start_phase("multiplicative_weights", 200, message="Searching for diverse committees")

    assert blocker.args == ["multiplicative_weights", 200, "Searching for diverse committees"]


def test_a_phase_with_no_total_says_so(qtbot, reporter: QtProgressReporter) -> None:
    """A convergence loop has no fixed end, and the bar has to know to go indeterminate."""
    with qtbot.waitSignal(reporter.phase_started, timeout=TIMEOUT_MS) as blocker:
        reporter.start_phase("maximin_optimization", None, message="Optimizing")

    assert blocker.args == ["maximin_optimization", None, "Optimizing"]


def test_an_update_carries_the_phase_total_with_it(qtbot, reporter: QtProgressReporter) -> None:
    reporter.start_phase("multiplicative_weights", 200, message="Searching")

    with qtbot.waitSignal(reporter.progressed, timeout=TIMEOUT_MS) as blocker:
        reporter.update(7, message="Round 7/200")

    assert blocker.args == [7, 200, "Round 7/200"]


def test_the_library_calling_without_a_message_is_survivable(qtbot, reporter: QtProgressReporter) -> None:
    """`message` is documented as always supplied, but the protocol allows None."""
    reporter.start_phase("diversimax", None)

    with qtbot.waitSignal(reporter.progressed, timeout=TIMEOUT_MS) as blocker:
        reporter.update(1)

    assert blocker.args == [1, None, ""]


def test_hammering_update_does_not_flood_the_event_queue(qtbot, reporter: QtProgressReporter) -> None:
    """The whole reason the throttle exists - one signal per library call would drown Qt."""
    emitted: list[int] = []
    reporter.progressed.connect(lambda current, total, message: emitted.append(current))

    reporter.start_phase("maximin_optimization", None, message="Optimizing")
    for current in range(2000):
        reporter.update(current, message=f"Iteration {current}")

    assert len(emitted) < 20


def test_ending_a_phase_reports_where_it_actually_finished(qtbot, reporter: QtProgressReporter) -> None:
    emitted: list[int] = []
    reporter.progressed.connect(lambda current, total, message: emitted.append(current))

    reporter.start_phase("multiplicative_weights", 200, message="Searching")
    for current in range(1, 201):
        reporter.update(current, message=f"Round {current}/200")
    reporter.end_phase()

    assert emitted[-1] == 200


def test_the_events_arrive_on_the_gui_thread(qtbot, reporter: QtProgressReporter) -> None:
    """
    The library drives the reporter from the worker thread; widgets only tolerate one.

    This is the test that would have caught a direct connection, which would run the
    slot on whichever thread emitted - and touching a widget from there is a crash.
    """
    seen: list[threading.Thread] = []
    reporter.phase_started.connect(lambda name, total, message: seen.append(threading.current_thread()))
    runner = QtTaskRunner()

    with qtbot.waitSignal(runner.finished, timeout=TIMEOUT_MS):
        runner.run(
            lambda: reporter.start_phase("multiplicative_weights", 200, message="Searching"),
            lambda result: None,
            lambda error: None,
        )
    qtbot.waitUntil(lambda: bool(seen), timeout=TIMEOUT_MS)

    assert seen[0] is threading.main_thread()


def test_connecting_through_the_helper_defers_the_slot(qtbot, reporter: QtProgressReporter) -> None:
    """
    A queued connection is what keeps the worker thread out of the widgets.

    It also means nothing a slot does - including raising - can reach back into the
    library's call stack and interrupt a ten minute selection, because emit() has
    already returned by the time the slot runs.
    """
    seen: list[str] = []
    reporter.connect_phase_started(lambda name, total, message: seen.append(name))

    reporter.start_phase("multiplicative_weights", 200, message="Searching")

    assert seen == []
    qtbot.waitUntil(lambda: seen == ["multiplicative_weights"], timeout=TIMEOUT_MS)
