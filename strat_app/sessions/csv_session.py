# ABOUTME: The CSV tab's logic - load categories and people, run a selection, offer the output.
# ABOUTME: Knows nothing about widgets; everything it wants to show goes through CsvView.

from io import StringIO
from typing import TYPE_CHECKING

from sortition_algorithms import adapters, core, features, people
from sortition_algorithms.utils import RunReport

from strat_app.sessions.log import GuiLog
from strat_app.sessions.tasks import SynchronousRunner, TaskRunner
from strat_app.sessions.view import CsvView, LogSection
from strat_app.settings_holder import SettingsHolder

if TYPE_CHECKING:
    from sortition_algorithms.progress import ProgressReporter

SELECTED_FILENAME = "selected.csv"
REMAINING_FILENAME = "remaining.csv"


class CsvSession:
    def __init__(
        self,
        view: CsvView,
        gui_log: GuiLog,
        settings_holder: SettingsHolder,
        runner: TaskRunner | None = None,
    ) -> None:
        self.view = view
        self.gui_log = gui_log
        self.settings_holder = settings_holder
        self.runner = runner or SynchronousRunner()
        # whoever builds the session supplies one that reaches the UI; None is fine and
        # means the library reports its progress to nobody
        self.progress_reporter: ProgressReporter | None = None
        self.data_source = adapters.CSVStringDataSource("", "")
        self.select_data = adapters.SelectionData(self.data_source)
        self.features: features.FeatureCollection | None = None
        self.people: people.People | None = None
        # cache this in case we need to reload
        self.people_contents: str = ""
        self.panel_size = 0  # Number of people in each panel

    def set_panel_size(self, panel_size: int) -> None:
        self.panel_size = panel_size
        self.update_run_button()

    def update_run_button(self) -> None:
        self.view.set_run_enabled(bool(self.features and self.people and self.panel_size > 0))

    def add_feature_content(self, file_contents: str) -> None:
        self.gui_log.reset(LogSection.CSV_FEATURES)
        if not file_contents:
            self.gui_log.add(LogSection.CSV_FEATURES, "No file contents - was the file empty?")
            return
        self.settings_holder.init_settings_log(self.gui_log, LogSection.CSV_FEATURES)
        if not self.settings_holder.loaded():
            return
        try:
            self.data_source.features_data = file_contents
            self.features, report = self.select_data.load_features()
            self.gui_log.add(LogSection.CSV_FEATURES, report)
        except Exception as error:
            self.gui_log.add(LogSection.CSV_FEATURES, f"Failed to load features: {error}")
        if not self.features:
            return
        self.view.set_people_input_enabled(enabled=True)
        min_size = features.minimum_selection(self.features)
        max_size = features.maximum_selection(self.features)
        self.view.set_panel_size_range(min_size, max_size)
        # if these are the same just set the value!
        if min_size == max_size and min_size > 0:
            self.panel_size = min_size
            self.view.set_panel_size(min_size)
        # reset people, might need to be reloaded with features
        if self.people:
            self.add_people_content(self.people_contents)

    def add_people_content(self, file_contents: str) -> None:
        self.gui_log.reset(LogSection.CSV_SELECTION)
        assert self.features is not None
        try:
            self.data_source.people_data = file_contents
            self.people, report = self.select_data.load_people(self.settings_holder.settings, self.features)
            # now we've done a successful load, cache the results
            self.people_contents = file_contents
            self.gui_log.add(LogSection.CSV_SELECTION, report)
            self.gui_log.add(LogSection.CSV_SELECTION, f"Loaded {self.people.count} people.")
            self.gui_log.add(LogSection.CSV_SELECTION, "Successfully loaded features and people.")
        except Exception as error:
            self.gui_log.add(LogSection.CSV_SELECTION, f"Failed to load people: {error}")
        self.update_run_button()

    def _fresh_output_buffers(self) -> None:
        """
        Start each run from empty output buffers.

        The data source appends to whatever is already in them, so without this a second
        run would leave you with both panels one after the other in the saved file.
        """
        self.data_source.selected_file = StringIO()
        self.data_source.remaining_file = StringIO()

    def run_selection(self, test_selection: bool) -> None:
        """
        Start a selection.

        The selection itself can take minutes, so it goes to the runner. Everything
        after it - reporting and writing the output - happens in the callbacks, back
        wherever the session lives.
        """
        assert self.people is not None and self.features is not None
        # they may have hit this button again, so clear the output area so it's more obvious
        self.gui_log.reset(LogSection.DETAILED_LOG, "Selecting... please wait...")
        self.view.set_busy(busy=True)
        self.runner.run(
            lambda: self._stratify(test_selection=test_selection),
            self._selection_finished,
            self._selection_failed,
        )

    def _stratify(self, *, test_selection: bool) -> tuple[bool, list[frozenset[str]], RunReport]:
        """Runs wherever the runner puts it - so it touches no view and no widget."""
        assert self.people is not None and self.features is not None
        return core.run_stratification(
            features=self.features,
            people=self.people,
            number_people_wanted=self.panel_size,
            settings=self.settings_holder.settings,
            test_selection=test_selection,
            progress_reporter=self.progress_reporter,
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
            self.gui_log.add(LogSection.DETAILED_LOG, "No panels written to CSV, process ended.")
            return
        try:
            self._write_output(people_selected[0])
        except Exception as err:
            self.gui_log.add_all(
                LogSection.DETAILED_LOG,
                [f"Unexpected error during writing selection: {err}", "Writing failed, process ended."],
            )
        finally:
            self.view.set_busy(busy=False)

    def _write_output(self, people_selected: frozenset[str]) -> None:
        """Writing a CSV to memory is quick, so this stays alongside the view."""
        assert self.people is not None and self.features is not None
        selected_rows, remaining_rows, _ = core.selected_remaining_tables(
            full_people=self.people,
            people_selected=people_selected,
            features=self.features,
            settings=self.settings_holder.settings,
        )
        self._fresh_output_buffers()
        self.select_data.output_selected_remaining(selected_rows, remaining_rows, self.settings_holder.settings)
        self.view.offer_selected(self.data_source.selected_file.getvalue(), SELECTED_FILENAME)
        self.view.offer_remaining(self.data_source.remaining_file.getvalue(), REMAINING_FILENAME)
