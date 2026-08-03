# ABOUTME: Unit tests for the CSV tab's logic, driven through a recording view.
# ABOUTME: No Qt, no network - these are the tests the eel app never had.

from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from strat_app.sessions.csv_session import CsvSession
from strat_app.sessions.log import GuiLog
from strat_app.sessions.view import LogSection
from strat_app.settings_holder import SettingsHolder
from tests.fakes import CallRecorder, RecordingLogView

if TYPE_CHECKING:
    from sortition_algorithms import people

PANEL_MIN = 22
PANEL_MAX = 24
PEOPLE_COUNT = 200


@pytest.fixture
def log() -> RecordingLogView:
    return RecordingLogView()


@pytest.fixture
def view() -> CallRecorder:
    return CallRecorder()


@pytest.fixture
def session(view: CallRecorder, log: RecordingLogView, settings_path: Path) -> CsvSession:
    return CsvSession(view, GuiLog(log), SettingsHolder(settings_path))


@pytest.fixture
def loaded_session(session: CsvSession, categories_contents: str, people_contents: str) -> CsvSession:
    session.add_feature_content(categories_contents)
    session.add_people_content(people_contents)
    return session


###########################
# loading the categories
###########################


def test_loading_categories_enables_people_input_and_sets_the_range(
    session: CsvSession,
    view: CallRecorder,
    log: RecordingLogView,
    categories_contents: str,
) -> None:
    session.add_feature_content(categories_contents)

    assert view.last_args("set_people_input_enabled") == (True,)
    assert view.last_args("set_panel_size_range") == (PANEL_MIN, PANEL_MAX)
    assert "Number of features found: 4" in log.text(LogSection.CSV_FEATURES)


def test_loading_categories_does_not_touch_the_run_button(
    session: CsvSession,
    view: CallRecorder,
    categories_contents: str,
) -> None:
    """Loading categories leaves the run button as it was - people are still needed."""
    session.add_feature_content(categories_contents)

    assert not view.called("set_run_enabled")


def test_empty_categories_file_reports_and_stops(
    session: CsvSession,
    view: CallRecorder,
    log: RecordingLogView,
) -> None:
    session.add_feature_content("")

    assert "No file contents - was the file empty?" in log.text(LogSection.CSV_FEATURES)
    assert not view.called("set_people_input_enabled")
    assert session.features is None


def test_unparseable_categories_file_reports_the_error(
    session: CsvSession,
    view: CallRecorder,
    log: RecordingLogView,
) -> None:
    session.add_feature_content("this is not,a categories csv\n1,2\n")

    assert "Failed to load features" in log.text(LogSection.CSV_FEATURES)
    assert not view.called("set_people_input_enabled")


def test_unreadable_settings_file_stops_the_load(
    view: CallRecorder,
    log: RecordingLogView,
    tmp_path: Path,
    categories_contents: str,
) -> None:
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text("this is not: valid toml [[[")
    session = CsvSession(view, GuiLog(log), SettingsHolder(settings_file))

    session.add_feature_content(categories_contents)

    assert "Error reading in settings file" in log.text(LogSection.CSV_FEATURES)
    assert session.features is None
    assert not view.called("set_people_input_enabled")


def test_categories_with_no_flexibility_set_the_panel_size(session: CsvSession, view: CallRecorder) -> None:
    """When min and max selection are equal there is only one possible size, so it is filled in."""
    categories = "category,name,min,max\ngender,Female,5,5\ngender,Male,5,5\n"

    session.add_feature_content(categories)

    assert view.last_args("set_panel_size") == (10,)
    assert session.panel_size == 10


#######################
# loading the people
#######################


def test_loading_people_reports_the_count(
    session: CsvSession,
    log: RecordingLogView,
    categories_contents: str,
    people_contents: str,
) -> None:
    session.add_feature_content(categories_contents)

    session.add_people_content(people_contents)

    selection_log = log.text(LogSection.CSV_SELECTION)
    assert f"Loaded {PEOPLE_COUNT} people." in selection_log
    assert "Successfully loaded features and people." in selection_log


def test_loading_people_before_categories_is_an_error(session: CsvSession, people_contents: str) -> None:
    """The people input is disabled until categories load, so this should be unreachable."""
    with pytest.raises(AssertionError):
        session.add_people_content(people_contents)


def test_people_that_do_not_match_the_categories_are_reported(
    session: CsvSession,
    view: CallRecorder,
    log: RecordingLogView,
    categories_contents: str,
) -> None:
    session.add_feature_content(categories_contents)

    session.add_people_content("nationbuilder_id,first_name\n1,Alice\n")

    assert "Failed to load people" in log.text(LogSection.CSV_SELECTION)
    assert view.last_args("set_run_enabled") == (False,)


def test_reloading_categories_reparses_the_people(
    loaded_session: CsvSession,
    log: RecordingLogView,
    categories_contents: str,
) -> None:
    """People are held as parsed data, so new categories mean the people must be read again."""
    loaded_session.add_feature_content(categories_contents)

    assert f"Loaded {PEOPLE_COUNT} people." in log.text(LogSection.CSV_SELECTION)


#####################
# the panel size
#####################


def test_setting_the_panel_size_is_not_echoed_back_to_the_view(loaded_session: CsvSession, view: CallRecorder) -> None:
    """The view is the source of truth while the user is choosing, so it is left alone."""
    loaded_session.set_panel_size(PANEL_MIN)

    assert not view.called("set_panel_size")


@pytest.mark.parametrize(
    ("with_features", "with_people", "panel_size", "expected"),
    [
        (False, False, 0, False),
        (False, False, PANEL_MIN, False),
        (False, True, PANEL_MIN, False),
        (True, False, PANEL_MIN, False),
        (True, True, 0, False),
        (True, True, PANEL_MIN, True),
    ],
)
def test_run_button_needs_categories_people_and_a_size(
    session: CsvSession,
    view: CallRecorder,
    categories_contents: str,
    with_features: bool,
    with_people: bool,
    panel_size: int,
    expected: bool,
) -> None:
    if with_features:
        session.add_feature_content(categories_contents)
    if with_people:
        # people are only loadable once features are, so set the state directly
        session.people = cast("people.People", object())

    session.set_panel_size(panel_size)

    assert view.last_args("set_run_enabled") == (expected,)


#####################
# running a selection
#####################


def test_running_a_selection_offers_both_outputs(loaded_session: CsvSession, view: CallRecorder) -> None:
    loaded_session.set_panel_size(PANEL_MIN)

    loaded_session.run_selection(test_selection=False)

    selected_contents, selected_name = view.last_args("offer_selected")
    remaining_contents, remaining_name = view.last_args("offer_remaining")
    assert selected_name == "selected.csv"
    assert remaining_name == "remaining.csv"
    # header row plus one row per person
    assert len(selected_contents.strip().splitlines()) == PANEL_MIN + 1
    assert len(remaining_contents.strip().splitlines()) == PEOPLE_COUNT - PANEL_MIN + 1


def test_a_selection_starts_by_clearing_the_log(loaded_session: CsvSession, log: RecordingLogView) -> None:
    loaded_session.set_panel_size(PANEL_MIN)

    loaded_session.run_selection(test_selection=False)

    assert log.entries(LogSection.DETAILED_LOG)[0] == "Selecting... please wait..."


def test_running_a_selection_twice_offers_only_the_second_panel(
    loaded_session: CsvSession,
    view: CallRecorder,
) -> None:
    """The old app appended the second run's output to the first, so pin the fix down."""
    loaded_session.set_panel_size(PANEL_MIN)

    loaded_session.run_selection(test_selection=False)
    loaded_session.run_selection(test_selection=False)

    selected_contents, _ = view.last_args("offer_selected")
    assert len(selected_contents.strip().splitlines()) == PANEL_MIN + 1


def test_the_selected_and_remaining_output_partitions_the_pool(loaded_session: CsvSession, view: CallRecorder) -> None:
    loaded_session.set_panel_size(PANEL_MIN)

    loaded_session.run_selection(test_selection=False)

    selected_ids = ids_from_csv(view.last_args("offer_selected")[0])
    remaining_ids = ids_from_csv(view.last_args("offer_remaining")[0])
    assert len(selected_ids) == PANEL_MIN
    assert not selected_ids & remaining_ids
    assert len(selected_ids | remaining_ids) == PEOPLE_COUNT


def ids_from_csv(contents: str) -> set[str]:
    lines = contents.strip().splitlines()
    return {line.split(",")[0] for line in lines[1:]}


def test_an_impossible_selection_offers_no_output(
    session: CsvSession,
    view: CallRecorder,
    log: RecordingLogView,
    categories_contents: str,
    people_too_few_contents: str,
) -> None:
    session.add_feature_content(categories_contents)
    session.add_people_content(people_too_few_contents)
    session.set_panel_size(PANEL_MIN)

    session.run_selection(test_selection=False)

    assert "No panels written to CSV, process ended." in log.text(LogSection.DETAILED_LOG)
    assert not view.called("offer_selected")


def test_an_error_during_selection_is_reported_and_leaves_the_app_usable(
    loaded_session: CsvSession,
    log: RecordingLogView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(**kwargs: object) -> None:
        msg = "the solver fell over"
        raise RuntimeError(msg)

    monkeypatch.setattr("strat_app.sessions.csv_session.core.run_stratification", explode)
    loaded_session.set_panel_size(PANEL_MIN)

    loaded_session.run_selection(test_selection=False)

    detailed_log = log.text(LogSection.DETAILED_LOG)
    assert "Unexpected error during selection: the solver fell over" in detailed_log
    assert "Selection failed, process ended." in detailed_log
    assert loaded_session.people is not None
