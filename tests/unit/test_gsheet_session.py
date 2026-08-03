# ABOUTME: Unit tests for the Google Sheet tab's logic, against a fixture-backed data source.
# ABOUTME: No credentials and no network, so the whole flow runs anywhere the suite does.

from pathlib import Path
from typing import cast

import gspread
import pytest
from sortition_algorithms import adapters

from strat_app.sessions.gsheet_session import GSheetSession
from strat_app.sessions.log import GuiLog
from strat_app.sessions.view import LogSection
from strat_app.settings_holder import SettingsHolder
from tests.fakes import CallRecorder, FakeGSheetDataSource, RecordingLogView

PANEL_MIN = 22
PANEL_MAX = 24
SHEET_NAME = "My Assembly"


@pytest.fixture
def log() -> RecordingLogView:
    return RecordingLogView()


@pytest.fixture
def view() -> CallRecorder:
    return CallRecorder()


@pytest.fixture
def data_source(categories_contents: str, people_contents: str) -> FakeGSheetDataSource:
    return FakeGSheetDataSource(
        tabs={"Categories": categories_contents, "Respondents": people_contents},
        sheet_names=[SHEET_NAME],
    )


def make_session(
    view: CallRecorder, log: RecordingLogView, settings_path: Path, data_source: FakeGSheetDataSource
) -> GSheetSession:
    """The fake stands in for a GSheetDataSource without inheriting from it, hence the cast."""
    return GSheetSession(
        view,
        GuiLog(log),
        SettingsHolder(settings_path),
        data_source=cast("adapters.GSheetDataSource", data_source),
    )


@pytest.fixture
def session(
    view: CallRecorder,
    log: RecordingLogView,
    settings_path: Path,
    data_source: FakeGSheetDataSource,
) -> GSheetSession:
    return make_session(view, log, settings_path, data_source)


@pytest.fixture
def loaded_session(session: GSheetSession) -> GSheetSession:
    session.update_g_sheet_name(SHEET_NAME)
    session.load_g_sheet()
    return session


############################
# the spreadsheet name
############################


def test_entering_a_sheet_name_enables_the_load_button(session: GSheetSession, view: CallRecorder) -> None:
    session.update_g_sheet_name(SHEET_NAME)

    assert view.last_args("set_load_enabled") == (True,)
    assert view.last_args("set_run_enabled") == (False,)


def test_clearing_the_sheet_name_leaves_the_load_button_alone(session: GSheetSession, view: CallRecorder) -> None:
    session.update_g_sheet_name("")

    assert not view.called("set_load_enabled")


def test_loading_with_no_sheet_name_asks_for_one(
    session: GSheetSession,
    view: CallRecorder,
    log: RecordingLogView,
) -> None:
    session.load_g_sheet()

    assert log.text(LogSection.GSHEET_FEATURES) == "Please enter a spreadsheet name..."
    assert not view.called("set_load_enabled")


def test_a_missing_spreadsheet_is_reported(
    session: GSheetSession,
    log: RecordingLogView,
    data_source: FakeGSheetDataSource,
) -> None:
    session.update_g_sheet_name("No Such Sheet")

    session.load_g_sheet()

    assert "Loading spreadsheet failed: Cannot find spreadsheet No Such Sheet" in log.text(LogSection.GSHEET_FEATURES)


###########################
# loading the spreadsheet
###########################


def test_loading_a_sheet_reports_categories_and_people(loaded_session: GSheetSession, log: RecordingLogView) -> None:
    assert "Number of features found: 4" in log.text(LogSection.GSHEET_FEATURES)
    assert "Successfully loaded features and people." in log.text(LogSection.GSHEET_SELECTION)


def test_loading_a_sheet_sets_the_panel_size_range(loaded_session: GSheetSession, view: CallRecorder) -> None:
    assert view.last_args("set_panel_size_range") == (PANEL_MIN, PANEL_MAX)


def test_a_missing_tab_is_reported_once(session: GSheetSession, log: RecordingLogView) -> None:
    session.update_g_sheet_name(SHEET_NAME)
    session.update_features_tab_name("Not A Tab")

    session.load_g_sheet()

    output = log.text(LogSection.GSHEET_FEATURES)
    assert "no tab called 'Not A Tab'" in output
    assert "Loading spreadsheet failed, see above messages." in output
    # KnownFailureError means the error is not reported a second time
    assert output.count("no tab called") == 1


def test_changing_the_categories_tab_resets_features_and_people(loaded_session: GSheetSession) -> None:
    loaded_session.update_features_tab_name("Other Categories")

    assert loaded_session.features is None
    assert loaded_session.people is None


def test_changing_the_respondents_tab_resets_only_the_people(loaded_session: GSheetSession) -> None:
    """Categories are unaffected by a different respondents tab, so they are kept."""
    loaded_session.update_people_tab_name("Other Respondents")

    assert loaded_session.features is not None
    assert loaded_session.people is None


def test_resetting_clears_the_range_before_the_size(loaded_session: GSheetSession, view: CallRecorder) -> None:
    """A view that clamps the size to the range can only go back to zero in that order."""
    view.reset()

    loaded_session.update_features_tab_name("Other Categories")

    assert view.names.index("set_panel_size_range") < view.names.index("set_panel_size")
    assert view.last_args("set_panel_size_range") == (0, 0)
    assert view.last_args("set_panel_size") == (0,)


###############################
# more than one selection
###############################


def test_asking_for_several_selections_warns_and_skips_the_remaining_tab(
    session: GSheetSession,
    log: RecordingLogView,
) -> None:
    session.update_g_sheet_name(SHEET_NAME)
    session.set_number_selections(2)

    session.load_g_sheet()

    assert "You've asked for 2 selections" in log.text(LogSection.GSHEET_SELECTION)
    assert session._safe_gen_rem_tab() is False  # noqa: SLF001


def test_one_selection_keeps_the_remaining_tab(session: GSheetSession) -> None:
    session.set_number_selections(1)

    assert session._safe_gen_rem_tab() is True  # noqa: SLF001


def test_turning_off_the_remaining_tab_is_respected(session: GSheetSession) -> None:
    session.update_gen_rem_tab(gen_rem_tab=False)

    assert session._safe_gen_rem_tab() is False  # noqa: SLF001


###########################
# running a selection
###########################


def test_running_a_selection_writes_the_output(
    loaded_session: GSheetSession,
    log: RecordingLogView,
    data_source: FakeGSheetDataSource,
) -> None:
    loaded_session.set_panel_size(PANEL_MIN)

    loaded_session.run_selection(test_selection=False)

    detailed_log = log.text(LogSection.DETAILED_LOG)
    assert "All spreadsheet writing has finished." in detailed_log
    assert "Selection process finished." in detailed_log
    written = data_source.selected_file.getvalue().strip().splitlines()
    assert written[0].startswith("nationbuilder_id")
    assert len(written) == PANEL_MIN + 1


def test_the_remaining_tab_reports_shared_addresses(
    loaded_session: GSheetSession,
    log: RecordingLogView,
    data_source: FakeGSheetDataSource,
) -> None:
    loaded_session.set_panel_size(PANEL_MIN)

    loaded_session.run_selection(test_selection=False)

    # nobody in the fixture shares an address, so there is nothing to highlight
    assert data_source.highlighted_dupes == []
    assert "there are 0 people who share the same address" in log.text(LogSection.DETAILED_LOG)


def test_an_impossible_selection_writes_nothing(
    view: CallRecorder,
    log: RecordingLogView,
    settings_path: Path,
    categories_contents: str,
    people_too_few_contents: str,
) -> None:
    data_source = FakeGSheetDataSource(
        tabs={"Categories": categories_contents, "Respondents": people_too_few_contents},
        sheet_names=[SHEET_NAME],
    )
    session = make_session(view, log, settings_path, data_source)
    session.update_g_sheet_name(SHEET_NAME)
    session.load_g_sheet()
    session.set_panel_size(PANEL_MIN)

    session.run_selection(test_selection=False)

    assert "No panels written to spreadsheet, process ended." in log.text(LogSection.DETAILED_LOG)
    assert data_source.selected_file.getvalue() == ""


def test_an_api_error_while_loading_explains_the_delay(
    session: GSheetSession,
    log: RecordingLogView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """gspread raises this when the sheet was written to moments ago."""

    class FakeResponse:
        status_code = 429
        text = "quota exceeded"

        def json(self) -> dict[str, object]:
            return {"error": {"code": 429, "message": "quota exceeded", "status": "RESOURCE_EXHAUSTED"}}

    def raise_api_error(*args: object, **kwargs: object) -> None:
        raise gspread.exceptions.APIError(FakeResponse())  # type: ignore[arg-type]

    monkeypatch.setattr(adapters.SelectionData, "load_features", raise_api_error)
    session.update_g_sheet_name(SHEET_NAME)

    session.load_g_sheet()

    output = log.text(LogSection.GSHEET_FEATURES)
    assert "API error causing delay" in output
    assert "Loading spreadsheet failed, see above messages." in output
