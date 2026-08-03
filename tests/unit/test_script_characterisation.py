# ABOUTME: Characterisation tests pinning down what the current eel app does, before the Qt port.
# ABOUTME: They record the calls script.py makes into the browser and assert on the sequence.

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

import script
from tests.fakes import CallRecorder, FakeGSheetDataSource

if TYPE_CHECKING:
    from sortition_algorithms import people

PANEL_MIN = 22
PANEL_MAX = 24


@pytest.fixture
def eel(monkeypatch: pytest.MonkeyPatch, settings_path: Path) -> Iterator[CallRecorder]:
    """
    Replace the eel module, and the module-level singletons that hang off it.

    script.py keeps its state in module globals, so each test needs fresh ones or the
    settings loaded by one test leak into the next.
    """
    recorder = CallRecorder()
    monkeypatch.setattr(script, "eel", recorder)
    monkeypatch.setattr(script, "gui_log", script.GuiLog())
    monkeypatch.setattr(script, "settings_holder", script.SettingsHolder())
    monkeypatch.setattr(script, "DEFAULT_SETTINGS_PATH", settings_path)
    yield recorder


@pytest.fixture
def csv_handler(eel: CallRecorder) -> script.CSVHandler:
    return script.CSVHandler()


@pytest.fixture
def loaded_csv_handler(
    csv_handler: script.CSVHandler,
    categories_contents: str,
    people_contents: str,
) -> script.CSVHandler:
    csv_handler.add_feature_content(categories_contents)
    csv_handler.add_people_content(people_contents)
    return csv_handler


def features_output(eel: CallRecorder) -> str:
    return eel.last_args("update_csv_features_output_area")[0]


def selection_output(eel: CallRecorder) -> str:
    return eel.last_args("update_csv_selection_output_area")[0]


def detailed_log(eel: CallRecorder) -> str:
    return eel.last_args("update_detailed_log_messages_area")[0]


###############################
# CSV tab - loading categories
###############################


def test_loading_categories_enables_people_input_and_sets_the_range(
    csv_handler: script.CSVHandler,
    eel: CallRecorder,
    categories_contents: str,
) -> None:
    csv_handler.add_feature_content(categories_contents)

    assert eel.called("enable_csv_selection_content")
    assert eel.last_args("update_csv_selection_range") == (PANEL_MIN, PANEL_MAX)
    assert "Number of features found: 4" in features_output(eel)


def test_loading_categories_does_not_touch_the_run_button(
    csv_handler: script.CSVHandler,
    eel: CallRecorder,
    categories_contents: str,
) -> None:
    """Loading categories leaves the run button as it was - people are still needed."""
    csv_handler.add_feature_content(categories_contents)

    assert not eel.called("enable_csv_run_button")
    assert not eel.called("disable_csv_run_button")


def test_empty_categories_file_reports_and_stops(csv_handler: script.CSVHandler, eel: CallRecorder) -> None:
    csv_handler.add_feature_content("")

    assert "No file contents - was the file empty?" in features_output(eel)
    assert not eel.called("enable_csv_selection_content")
    assert csv_handler.features is None


def test_unparseable_categories_file_reports_the_error(csv_handler: script.CSVHandler, eel: CallRecorder) -> None:
    csv_handler.add_feature_content("this is not,a categories csv\n1,2\n")

    assert "Failed to load features" in features_output(eel)
    assert not eel.called("enable_csv_selection_content")


def test_categories_with_no_flexibility_set_the_panel_size(csv_handler: script.CSVHandler, eel: CallRecorder) -> None:
    """When min and max selection are equal there is only one possible size, so it is filled in."""
    categories = "category,name,min,max\ngender,Female,5,5\ngender,Male,5,5\n"

    csv_handler.add_feature_content(categories)

    assert eel.last_args("set_csv_panel_size") == ("10",)
    assert csv_handler.panel_size_num == 10


###########################
# CSV tab - loading people
###########################


def test_loading_people_reports_the_count(
    csv_handler: script.CSVHandler,
    eel: CallRecorder,
    categories_contents: str,
    people_contents: str,
) -> None:
    csv_handler.add_feature_content(categories_contents)

    csv_handler.add_people_content(people_contents)

    assert "Loaded 200 people." in selection_output(eel)
    assert "Successfully loaded features and people." in selection_output(eel)


def test_loading_people_before_categories_is_an_error(csv_handler: script.CSVHandler, people_contents: str) -> None:
    """The people input is disabled until categories load, so this should be unreachable."""
    with pytest.raises(AssertionError):
        csv_handler.add_people_content(people_contents)


def test_people_that_do_not_match_the_categories_are_reported(
    csv_handler: script.CSVHandler,
    eel: CallRecorder,
    categories_contents: str,
) -> None:
    csv_handler.add_feature_content(categories_contents)

    csv_handler.add_people_content("nationbuilder_id,first_name\n1,Alice\n")

    assert "Failed to load people" in selection_output(eel)
    assert eel.names[-1] == "disable_csv_run_button"


def test_reloading_categories_reparses_the_people(
    loaded_csv_handler: script.CSVHandler,
    eel: CallRecorder,
    categories_contents: str,
) -> None:
    """People are held as parsed data, so new categories mean the people must be read again."""
    eel.reset()

    loaded_csv_handler.add_feature_content(categories_contents)

    assert "Loaded 200 people." in selection_output(eel)


############################
# CSV tab - the panel size
############################


@pytest.mark.parametrize(
    ("typed", "expected_num"),
    [("22", 22), (" 22 ", 22), ("", 0), ("nonsense", 0), ("-5", 0)],
)
def test_panel_size_parsing(
    loaded_csv_handler: script.CSVHandler,
    eel: CallRecorder,
    typed: str,
    expected_num: int,
) -> None:
    loaded_csv_handler.update_panel_size(typed)

    assert loaded_csv_handler.panel_size_num == expected_num


def test_typing_a_panel_size_does_not_write_back_to_the_input(
    loaded_csv_handler: script.CSVHandler,
    eel: CallRecorder,
) -> None:
    """Writing back while the user types would fight with them, so the app deliberately doesn't."""
    eel.reset()

    loaded_csv_handler.update_panel_size("nonsense")

    assert not eel.called("set_csv_panel_size")


@pytest.mark.parametrize(
    ("with_features", "with_people", "panel_size", "expected"),
    [
        (False, False, "0", "disable_csv_run_button"),
        (False, False, "22", "disable_csv_run_button"),
        (False, True, "22", "disable_csv_run_button"),
        (True, False, "22", "disable_csv_run_button"),
        (True, True, "0", "disable_csv_run_button"),
        (True, True, "", "disable_csv_run_button"),
        (True, True, "22", "enable_csv_run_button"),
    ],
)
def test_run_button_needs_categories_people_and_a_size(
    csv_handler: script.CSVHandler,
    eel: CallRecorder,
    categories_contents: str,
    people_contents: str,
    with_features: bool,
    with_people: bool,
    panel_size: str,
    expected: str,
) -> None:
    if with_features:
        csv_handler.add_feature_content(categories_contents)
    if with_people:
        # people are only loadable once features are, so set the state directly
        csv_handler.people = cast("people.People", object())
    csv_handler.update_panel_size(panel_size)

    assert eel.names[-1] == expected


##########################
# CSV tab - the selection
##########################


def test_running_a_selection_offers_both_downloads(loaded_csv_handler: script.CSVHandler, eel: CallRecorder) -> None:
    loaded_csv_handler.update_panel_size(str(PANEL_MIN))

    loaded_csv_handler.run_selection(test_selection=False)

    selected_contents, selected_name = eel.last_args("enable_csv_selected_download")
    remaining_contents, remaining_name = eel.last_args("enable_csv_remaining_download")
    assert selected_name == "selected.csv"
    assert remaining_name == "remaining.csv"
    # header row plus one row per person
    assert len(selected_contents.strip().splitlines()) == PANEL_MIN + 1
    assert len(remaining_contents.strip().splitlines()) == 200 - PANEL_MIN + 1


def test_a_selection_starts_by_clearing_the_log(loaded_csv_handler: script.CSVHandler, eel: CallRecorder) -> None:
    loaded_csv_handler.update_panel_size(str(PANEL_MIN))
    eel.reset()

    loaded_csv_handler.run_selection(test_selection=False)

    assert eel.args_for("update_detailed_log_messages_area")[0] == ("Selecting... please wait...<br />",)


def test_an_impossible_selection_offers_no_downloads(
    csv_handler: script.CSVHandler,
    eel: CallRecorder,
    categories_contents: str,
    people_too_few_contents: str,
) -> None:
    csv_handler.add_feature_content(categories_contents)
    csv_handler.add_people_content(people_too_few_contents)
    csv_handler.update_panel_size(str(PANEL_MIN))

    csv_handler.run_selection(test_selection=False)

    assert "No panels written to CSV, process ended." in detailed_log(eel)
    assert not eel.called("enable_csv_selected_download")


def test_an_error_during_selection_is_reported_and_leaves_the_app_usable(
    loaded_csv_handler: script.CSVHandler,
    eel: CallRecorder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(**kwargs: object) -> None:
        msg = "the solver fell over"
        raise RuntimeError(msg)

    monkeypatch.setattr(script.core, "run_stratification", explode)
    loaded_csv_handler.update_panel_size(str(PANEL_MIN))

    loaded_csv_handler.run_selection(test_selection=False)

    assert "Unexpected error during selection: the solver fell over" in detailed_log(eel)
    assert "Selection failed, process ended." in detailed_log(eel)
    assert loaded_csv_handler.people is not None


######################################
# G Sheet tab - names and tab names
######################################


@pytest.fixture
def g_sheet_handler(eel: CallRecorder, categories_contents: str, people_contents: str) -> script.GSheetHandler:
    handler = script.GSheetHandler()
    handler.data_source = FakeGSheetDataSource(
        tabs={"Categories": categories_contents, "Respondents": people_contents},
        sheet_names=["My Assembly"],
    )
    handler.select_data = script.adapters.SelectionData(handler.data_source)
    return handler


def g_sheet_features_output(eel: CallRecorder) -> str:
    return eel.last_args("update_g_sheet_features_output_area")[0]


def g_sheet_selection_output(eel: CallRecorder) -> str:
    return eel.last_args("update_g_sheet_selection_output_area")[0]


def test_entering_a_sheet_name_enables_the_load_button(
    g_sheet_handler: script.GSheetHandler,
    eel: CallRecorder,
) -> None:
    g_sheet_handler.update_g_sheet_name("My Assembly")

    assert eel.called("enable_load_g_sheet_btn")
    assert eel.called("disable_g_sheet_run_button")


def test_clearing_the_sheet_name_leaves_the_load_button_alone(
    g_sheet_handler: script.GSheetHandler,
    eel: CallRecorder,
) -> None:
    g_sheet_handler.update_g_sheet_name("")

    assert not eel.called("enable_load_g_sheet_btn")


def test_loading_with_no_sheet_name_asks_for_one(g_sheet_handler: script.GSheetHandler, eel: CallRecorder) -> None:
    g_sheet_handler.load_g_sheet()

    assert g_sheet_features_output(eel) == "Please enter a spreadsheet name..."
    assert not eel.called("enable_load_g_sheet_btn")


def test_loading_a_sheet_reports_categories_and_people(
    g_sheet_handler: script.GSheetHandler,
    eel: CallRecorder,
) -> None:
    g_sheet_handler.update_g_sheet_name("My Assembly")

    g_sheet_handler.load_g_sheet()

    assert "Number of features found: 4" in g_sheet_features_output(eel)
    assert "Successfully loaded features and people." in g_sheet_selection_output(eel)
    assert eel.last_args("update_g_sheet_selection_range") == (PANEL_MIN, PANEL_MAX)


def test_a_missing_tab_is_reported_once(g_sheet_handler: script.GSheetHandler, eel: CallRecorder) -> None:
    g_sheet_handler.update_g_sheet_name("My Assembly")
    g_sheet_handler.update_features_tab_name("Not A Tab")

    g_sheet_handler.load_g_sheet()

    output = g_sheet_features_output(eel)
    assert "no tab called 'Not A Tab'" in output
    assert "Loading spreadsheet failed, see above messages." in output
    # KnownFailureError means the error is not reported a second time
    assert output.count("no tab called") == 1


def test_changing_the_categories_tab_resets_features_and_people(g_sheet_handler: script.GSheetHandler) -> None:
    g_sheet_handler.update_g_sheet_name("My Assembly")
    g_sheet_handler.load_g_sheet()

    g_sheet_handler.update_features_tab_name("Other Categories")

    assert g_sheet_handler.features is None
    assert g_sheet_handler.people is None


def test_changing_the_respondents_tab_resets_only_the_people(g_sheet_handler: script.GSheetHandler) -> None:
    """Categories are unaffected by a different respondents tab, so they are kept."""
    g_sheet_handler.update_g_sheet_name("My Assembly")
    g_sheet_handler.load_g_sheet()

    g_sheet_handler.update_people_tab_name("Other Respondents")

    assert g_sheet_handler.features is not None
    assert g_sheet_handler.people is None


def test_asking_for_several_selections_warns_and_skips_the_remaining_tab(
    g_sheet_handler: script.GSheetHandler,
    eel: CallRecorder,
) -> None:
    g_sheet_handler.update_g_sheet_name("My Assembly")
    g_sheet_handler.update_number_selections("2")

    g_sheet_handler.load_g_sheet()

    assert "You've asked for 2 selections" in g_sheet_selection_output(eel)
    assert g_sheet_handler._safe_gen_rem_tab() is False  # noqa: SLF001


def test_a_blank_number_of_selections_means_one(g_sheet_handler: script.GSheetHandler) -> None:
    g_sheet_handler.update_number_selections("")

    assert g_sheet_handler.number_selections == 1


def test_running_a_g_sheet_selection_writes_the_output(
    g_sheet_handler: script.GSheetHandler,
    eel: CallRecorder,
) -> None:
    g_sheet_handler.update_g_sheet_name("My Assembly")
    g_sheet_handler.load_g_sheet()
    g_sheet_handler.update_panel_size(str(PANEL_MIN))

    g_sheet_handler.run_selection(test_selection=False)

    log = detailed_log(eel)
    assert "All spreadsheet writing has finished." in log
    assert "Selection process finished." in log
    assert g_sheet_handler.data_source.selected_file.getvalue().strip().splitlines()[0].startswith("nationbuilder_id")


def test_running_a_selection_twice_appends_to_the_first_output(
    loaded_csv_handler: script.CSVHandler,
    eel: CallRecorder,
) -> None:
    """
    BUG, documented rather than endorsed.

    CSVStringDataSource writes into a StringIO that is never truncated, so a second
    run leaves the download containing both panels one after the other. The Qt port
    writes to a file the user picks in a save dialog, which fixes this.
    """
    loaded_csv_handler.update_panel_size(str(PANEL_MIN))

    loaded_csv_handler.run_selection(test_selection=False)
    loaded_csv_handler.run_selection(test_selection=False)

    selected_contents, _ = eel.last_args("enable_csv_selected_download")
    assert len(selected_contents.strip().splitlines()) == (PANEL_MIN + 1) * 2
