# ABOUTME: Unit tests for the throttle that stands between the library and the GUI thread.
# ABOUTME: No Qt here - the deciding is pure, so it is tested against a clock we control.

import pytest

from strat_app.sessions.progress import PhaseStart, ProgressThrottle, ProgressUpdate

INTERVAL = 0.1


class FakeClock:
    """A clock that only moves when a test says so."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def throttle(clock: FakeClock) -> ProgressThrottle:
    return ProgressThrottle(min_interval_seconds=INTERVAL, now=clock)


def test_a_phase_start_always_goes_through(throttle: ProgressThrottle) -> None:
    assert throttle.start_phase("multiplicative_weights", 200, "Searching") == PhaseStart(
        name="multiplicative_weights", total=200, message="Searching"
    )


def test_the_first_update_in_a_phase_goes_through(throttle: ProgressThrottle) -> None:
    throttle.start_phase("multiplicative_weights", 200, "Searching")

    assert throttle.update(1, "Round 1/200") == ProgressUpdate(current=1, total=200, message="Round 1/200")


def test_a_second_update_too_soon_is_dropped(throttle: ProgressThrottle, clock: FakeClock) -> None:
    throttle.start_phase("multiplicative_weights", 200, "Searching")
    throttle.update(1, "Round 1/200")

    clock.advance(INTERVAL / 2)

    assert throttle.update(2, "Round 2/200") is None


def test_an_update_after_the_interval_goes_through(throttle: ProgressThrottle, clock: FakeClock) -> None:
    throttle.start_phase("multiplicative_weights", 200, "Searching")
    throttle.update(1, "Round 1/200")

    clock.advance(INTERVAL)

    assert throttle.update(2, "Round 2/200") is not None


def test_hammering_update_is_bounded_by_the_clock(throttle: ProgressThrottle, clock: FakeClock) -> None:
    """
    The library calls update() every iteration and explicitly does not throttle.

    Its own docs say that can be hundreds of times per second on a fast solver. One Qt
    signal per call would flood the GUI thread's event queue, so this is the test that
    stops a later refactor quietly removing the throttle.
    """
    throttle.start_phase("maximin_optimization", None, "Optimizing")
    let_through = 0

    for current in range(1000):
        if throttle.update(current, f"Round {current}") is not None:
            let_through += 1
        clock.advance(INTERVAL / 100)

    assert let_through == pytest.approx(10, abs=1)


def test_a_phase_start_is_not_throttled_away_behind_an_update(throttle: ProgressThrottle, clock: FakeClock) -> None:
    """A phase change is what the label shows, so it must never wait for the interval."""
    throttle.start_phase("multiplicative_weights", 200, "Searching")
    throttle.update(1, "Round 1/200")

    assert throttle.start_phase("maximin_optimization", None, "Optimizing") is not None


def test_the_first_update_of_a_new_phase_is_not_throttled(throttle: ProgressThrottle) -> None:
    throttle.start_phase("multiplicative_weights", 200, "Searching")
    throttle.update(1, "Round 1/200")
    throttle.start_phase("maximin_optimization", None, "Optimizing")

    assert throttle.update(1, "Iteration 1") is not None


def test_ending_a_phase_reports_the_last_value_even_if_it_was_throttled(
    throttle: ProgressThrottle, clock: FakeClock
) -> None:
    """Otherwise a determinate bar stops at whatever it happened to be showing."""
    throttle.start_phase("multiplicative_weights", 200, "Searching")
    throttle.update(1, "Round 1/200")
    clock.advance(INTERVAL / 2)
    throttle.update(200, "Round 200/200")

    assert throttle.end_phase() == ProgressUpdate(current=200, total=200, message="Round 200/200")


def test_ending_a_phase_whose_last_value_was_already_reported_says_nothing(
    throttle: ProgressThrottle, clock: FakeClock
) -> None:
    throttle.start_phase("multiplicative_weights", 200, "Searching")
    clock.advance(INTERVAL)
    throttle.update(200, "Round 200/200")

    assert throttle.end_phase() is None


def test_ending_a_phase_with_no_updates_says_nothing(throttle: ProgressThrottle) -> None:
    throttle.start_phase("diversimax", None, "Solving")

    assert throttle.end_phase() is None


def test_an_update_outside_any_phase_is_ignored(throttle: ProgressThrottle) -> None:
    """The library should not do this, but a reporter that crashes on it helps nobody."""
    assert throttle.update(1, "Round 1") is None


def test_the_total_comes_from_the_phase_not_the_update(throttle: ProgressThrottle) -> None:
    throttle.start_phase("maximin_optimization", None, "Optimizing")

    update = throttle.update(7, "Iteration 7")

    assert update is not None
    assert update.total is None
