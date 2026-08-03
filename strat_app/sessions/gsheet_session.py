# ABOUTME: The Google Sheet tab's logic - read categories and people from tabs, write the output back.
# ABOUTME: Knows nothing about widgets; everything it wants to show goes through GSheetView.

from pathlib import Path
from typing import Any, NamedTuple

import gspread
from sortition_algorithms import adapters, core, features, people
from sortition_algorithms.utils import ReportLevel, RunReport

from strat_app.sessions.log import GuiLog
from strat_app.sessions.tasks import SynchronousRunner, TaskRunner
from strat_app.sessions.view import GSheetView, LogSection
from strat_app.settings_holder import SettingsHolder

DEFAULT_AUTH_JSON_PATH = Path.home() / "secret_do_not_commit.json"


class KnownFailureError(Exception):
    """
    Raised when the failure has already been reported, so nobody reports it twice.

    Carries the section it was reported in only so the caller does not have to guess.
    """

    def __init__(self, section: LogSection = LogSection.GSHEET_FEATURES) -> None:
        super().__init__("already reported")
        self.section = section


class LoadedSheet(NamedTuple):
    """What reading a spreadsheet gives us, ready to be applied to the session."""

    features: features.FeatureCollection
    people: people.People


class GSheetSession:
    clear_message = "Number of features: You must (re)load sheet..."

    def __init__(
        self,
        view: GSheetView,
        gui_log: GuiLog,
        settings_holder: SettingsHolder,
        data_source: adapters.GSheetDataSource | None = None,
        runner: TaskRunner | None = None,
    ) -> None:
        self.view = view
        self.gui_log = gui_log
        self.settings_holder = settings_holder
        self.runner = runner or SynchronousRunner()
        # the library grows a progress_reporter argument in 0.12; until then this stays
        # None and the busy indicator is all the feedback we can give during a run
        self.progress_reporter: Any = None
        # injectable so tests can drive the whole flow against a fake spreadsheet
        self.data_source = data_source or adapters.GSheetDataSource(
            feature_tab_name="",
            people_tab_name="",
            auth_json_path=DEFAULT_AUTH_JSON_PATH,
        )
        self.select_data = adapters.SelectionData(self.data_source)
        self.features: features.FeatureCollection | None = None
        self.people: people.People | None = None
        self.g_sheet_name = ""
        self.features_tab_name = "Categories"
        self.people_tab_name = "Respondents"
        self.gen_rem_tab = True
        self.number_selections = 1  # How many panels to create
        self.panel_size = 0  # Number of people in each panel

    def _clear_messages(self, features_message: str = clear_message) -> None:
        """Clear all messages (and optionally put a new message in place)"""
        self.gui_log.reset(LogSection.GSHEET_FEATURES, features_message)
        self.gui_log.reset(LogSection.GSHEET_SELECTION)
        self.gui_log.reset(LogSection.DETAILED_LOG)
        self._reset_panel_size()

    def _reset_panel_size(self) -> None:
        """
        Nothing is loaded, so there is no panel size and no range to choose from.

        The range has to be cleared before the size, or a view that clamps the size to
        the range - which is the whole point of clamping - would refuse to go back to 0.
        """
        self.panel_size = 0
        self.view.set_panel_size_range(0, 0)
        self.view.set_panel_size(0)

    def _reset_spreadsheet(self, *, reset_features: bool = True) -> None:
        if reset_features:
            self.features = None
        self.people = None
        self._reset_panel_size()
        self.update_run_button()

    def update_g_sheet_name(self, g_sheet_name: str) -> None:
        self._clear_messages()
        self._reset_spreadsheet()
        self.g_sheet_name = g_sheet_name
        if self.g_sheet_name != "":
            self.view.set_load_enabled(enabled=True)

    def set_panel_size(self, panel_size: int) -> None:
        self.panel_size = panel_size
        self.update_run_button()

    def update_run_button(self) -> None:
        self.view.set_run_enabled(bool(self.features and self.people and self.panel_size > 0))

    def update_people_tab_name(self, people_tab_name: str) -> None:
        self._clear_messages()
        self._reset_spreadsheet(reset_features=False)
        self.people_tab_name = people_tab_name

    def update_features_tab_name(self, features_tab_name: str) -> None:
        self._clear_messages()
        self._reset_spreadsheet()
        self.features_tab_name = features_tab_name

    def update_gen_rem_tab(self, gen_rem_tab: bool) -> None:
        self.gen_rem_tab = gen_rem_tab

    def _safe_gen_rem_tab(self) -> bool:
        """Get self.gen_rem_tab - but set to false if number_selections > 1"""
        # never generate a remaining tab if doing a multiple selection
        if self.number_selections > 1:
            return False
        return self.gen_rem_tab

    def set_number_selections(self, number_selections: int) -> None:
        self._clear_messages()
        self.number_selections = number_selections

    def _multiple_selections_warning(self) -> RunReport:
        report = RunReport()
        report.add_line(
            f"WARNING: You've asked for {self.number_selections} selections. "
            f"You cannot use the 'Produce a Test Panel' button if you want more "
            f"than 1 selection and no Remaining tab will be created.",
            level=ReportLevel.IMPORTANT,
        )
        return report

    # do features and people at same time...
    def load_g_sheet(self) -> None:
        """
        Start reading the spreadsheet.

        Talking to Google is slow enough to be worth keeping off the GUI thread, so
        the reading goes to the runner and the results are applied in the callbacks.
        """
        # forget about any previously loaded spreadsheet, and disable the run button
        self._reset_spreadsheet()
        # this can happen if they enter something and then delete it...
        if self.g_sheet_name == "":
            self._clear_messages("Please enter a spreadsheet name...")
            return
        self._clear_messages(f"Requesting category data from spreadsheet tab {self.features_tab_name} ...")
        self.settings_holder.init_settings_log(self.gui_log, LogSection.GSHEET_FEATURES)
        if not self.settings_holder.loaded():
            return
        if self.number_selections > 1:
            self.gui_log.add(LogSection.GSHEET_SELECTION, self._multiple_selections_warning())
        self.view.set_busy(busy=True)
        self.runner.run(self._read_sheet, self._sheet_loaded, self._sheet_failed)

    def _read_sheet(self) -> LoadedSheet:
        """
        Runs wherever the runner puts it - so no view calls, only the log.

        The log is safe to write to from anywhere, and these messages are the only
        sign of life while the spreadsheet is being read.
        """
        self.data_source.set_g_sheet_name(self.g_sheet_name)
        loaded_features = self._read_features()
        self.gui_log.add(
            LogSection.GSHEET_SELECTION,
            f"Requesting people data from spreadsheet tab {self.people_tab_name} ...",
        )
        return LoadedSheet(loaded_features, self._read_people(loaded_features))

    def _read_features(self) -> features.FeatureCollection:
        try:
            self.data_source.feature_tab_name = self.features_tab_name
            loaded_features, report = self.select_data.load_features()
            self.gui_log.add(LogSection.GSHEET_FEATURES, report)
        except gspread.exceptions.APIError as error:
            self.gui_log.add(
                LogSection.GSHEET_FEATURES,
                f"API error causing delay. Please wait a couple of seconds while gsheet updates. "
                f"After waiting you may need to reload sheet. "
                f"For the record, the API error is {error}",
            )
            raise KnownFailureError from error
        except Exception as error:
            self.gui_log.add(LogSection.GSHEET_FEATURES, f"Failed to load features: {error}")
            raise KnownFailureError from error
        if not loaded_features:
            self.gui_log.add(LogSection.GSHEET_FEATURES, "Failed to load features")
            raise KnownFailureError
        return loaded_features

    def _read_people(self, loaded_features: features.FeatureCollection) -> people.People:
        try:
            self.data_source.people_tab_name = self.people_tab_name
            loaded_people, report = self.select_data.load_people(self.settings_holder.settings, loaded_features)
            self.gui_log.add(LogSection.GSHEET_SELECTION, report)
        except Exception as error:
            self.gui_log.add(LogSection.GSHEET_SELECTION, f"Failed to load people: {error}")
            raise KnownFailureError(LogSection.GSHEET_SELECTION) from error
        if not loaded_people:
            self.gui_log.add(LogSection.GSHEET_SELECTION, "Failed to load people")
            raise KnownFailureError(LogSection.GSHEET_SELECTION)
        return loaded_people

    def _sheet_loaded(self, loaded: LoadedSheet) -> None:
        self.view.set_busy(busy=False)
        self.features = loaded.features
        self.people = loaded.people
        min_size = features.minimum_selection(self.features)
        max_size = features.maximum_selection(self.features)
        self.view.set_panel_size_range(min_size, max_size)
        # if these are the same just set the value!
        if min_size == max_size and min_size > 0:
            self.panel_size = min_size
            self.view.set_panel_size(min_size)
        self.gui_log.add(LogSection.GSHEET_SELECTION, "Successfully loaded features and people.")
        self.update_run_button()
        self.view.set_load_enabled(enabled=True)

    def _sheet_failed(self, error: Exception) -> None:
        self.view.set_busy(busy=False)
        if isinstance(error, KnownFailureError):
            # whatever raised this has already said what went wrong, so don't repeat it
            self.gui_log.add_all(
                LogSection.GSHEET_FEATURES,
                ["Loading spreadsheet failed, see above messages.", "Fix the problems and try loading again."],
            )
            return
        self.gui_log.add(LogSection.GSHEET_FEATURES, f"Loading spreadsheet failed: {error}")

    def run_selection(self, test_selection: bool) -> None:
        assert self.features is not None and self.people is not None
        self.gui_log.reset(LogSection.DETAILED_LOG, "Selecting... please wait...")
        self.view.set_busy(busy=True)
        self.runner.run(
            lambda: self._stratify(test_selection=test_selection),
            self._selection_finished,
            self._selection_failed,
        )

    def _stratify(self, *, test_selection: bool) -> tuple[bool, list[frozenset[str]], RunReport]:
        """Runs wherever the runner puts it - so it touches no view and no widget."""
        assert self.features is not None and self.people is not None
        extra = {"progress_reporter": self.progress_reporter} if self.progress_reporter else {}
        return core.run_stratification(
            features=self.features,
            people=self.people,
            number_people_wanted=self.panel_size,
            settings=self.settings_holder.settings,
            test_selection=test_selection,
            number_selections=self.number_selections,
            **extra,
        )

    def _selection_failed(self, error: Exception) -> None:
        self.view.set_busy(busy=False)
        self.gui_log.add_all(
            LogSection.DETAILED_LOG,
            [f"Unexpected error during selection: {error}", "Selection failed, process ended."],
        )

    def _selection_finished(self, result: tuple[bool, list[frozenset[str]], RunReport]) -> None:
        success, people_selected, report = result
        self.gui_log.add(LogSection.DETAILED_LOG, report)
        if not success:
            self.view.set_busy(busy=False)
            self.gui_log.add(LogSection.DETAILED_LOG, "No panels written to spreadsheet, process ended.")
            return

        self.gui_log.add(LogSection.DETAILED_LOG, "About to write to spreadsheet.")
        # writing goes back to the runner - it is several round trips to Google
        self.runner.run(
            lambda: self._write_output(people_selected[0]),
            self._writing_finished,
            self._writing_failed,
        )

    def _write_output(self, people_selected: frozenset[str]) -> tuple[list[int], RunReport]:
        assert self.features is not None and self.people is not None
        selected_rows, remaining_rows, _ = core.selected_remaining_tables(
            full_people=self.people,
            people_selected=people_selected,
            features=self.features,
            settings=self.settings_holder.settings,
        )
        self.select_data.gen_rem_tab = self._safe_gen_rem_tab()
        return self.select_data.output_selected_remaining(
            selected_rows,
            remaining_rows,
            self.settings_holder.settings,
        )

    def _writing_finished(self, result: tuple[list[int], RunReport]) -> None:
        dupes, report = result
        self.view.set_busy(busy=False)
        self.gui_log.add(LogSection.DETAILED_LOG, report)
        self.gui_log.add(
            LogSection.DETAILED_LOG,
            f"In the remaining tab there are {len(dupes)} people who share the same address as "
            f"someone else in the tab. They are highlighted in orange.",
        )
        self.gui_log.add(LogSection.DETAILED_LOG, "All spreadsheet writing has finished.")
        self.gui_log.add(LogSection.DETAILED_LOG, "Selection process finished.")

    def _writing_failed(self, error: Exception) -> None:
        self.view.set_busy(busy=False)
        self.gui_log.add_all(
            LogSection.DETAILED_LOG,
            [f"Unexpected error during writing selection: {error}", "Writing failed, process ended."],
        )
