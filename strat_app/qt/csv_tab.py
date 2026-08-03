# ABOUTME: The CSV tab - choose two CSV files, run a selection, save the two outputs.
# ABOUTME: Implements CsvView; file dialogs are kept in slots of their own so tests can skip them.

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from strat_app.qt.report_view import ReportBrowser

if TYPE_CHECKING:
    from strat_app.sessions.csv_session import CsvSession

CSV_FILE_FILTER = "CSV files (*.csv);;All files (*)"
PANEL_SIZE_LABEL = "Specify the number of people to select"
NO_FILE_CHOSEN = "No file chosen"


class CsvTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._session: CsvSession | None = None
        self._run_enabled_before_busy = False
        self._selected_contents = ""
        self._selected_filename = "selected.csv"
        self._remaining_contents = ""
        self._remaining_filename = "remaining.csv"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Option A: CSV file input and output</h2>"))
        layout.addWidget(self._build_file_inputs())
        layout.addWidget(self._build_information())
        layout.addWidget(self._build_selection())
        layout.addWidget(self._build_output())
        layout.addStretch()

        self._connect_signals()

    ###############
    # the widgets
    ###############

    def _build_file_inputs(self) -> QGroupBox:
        box = QGroupBox()
        layout = QVBoxLayout(box)

        layout.addWidget(QLabel("Step 1: Select a CSV file with feature/category information"))
        self.features_button = QPushButton("Choose categories file…")
        self.features_label = QLabel(NO_FILE_CHOSEN)
        layout.addLayout(_row(self.features_button, self.features_label))

        layout.addWidget(QLabel("Step 2: Select a CSV file with people to select from"))
        self.people_button = QPushButton("Choose people file…")
        self.people_button.setEnabled(False)
        self.people_label = QLabel(NO_FILE_CHOSEN)
        layout.addLayout(_row(self.people_button, self.people_label))
        return box

    def _build_information(self) -> QGroupBox:
        box = QGroupBox("Category and people information:")
        layout = QVBoxLayout(box)
        self.features_output = ReportBrowser()
        self.features_output.show_entries(["Number of categories: No input yet"])
        self.people_output = ReportBrowser()
        self.people_output.show_entries(["Number of people: No input yet"])
        layout.addWidget(self.features_output)
        layout.addWidget(self.people_output)
        return box

    def _build_selection(self) -> QGroupBox:
        box = QGroupBox("Set number of people and run selection")
        layout = QVBoxLayout(box)
        self.panel_size_label = QLabel(PANEL_SIZE_LABEL)
        self.panel_size_spin = QSpinBox()
        self.panel_size_spin.setRange(0, 0)
        layout.addWidget(self.panel_size_label)
        layout.addWidget(self.panel_size_spin)

        self.run_button = QPushButton("Run the Random Selection")
        self.run_test_button = QPushButton("(Produce a Test Panel)")
        self.set_run_enabled(enabled=False)
        layout.addLayout(_row(self.run_button, self.run_test_button))
        self.busy_bar = QProgressBar()
        # no phases or percentages from the library at this version, so all we can
        # honestly show is that something is happening
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setVisible(False)
        layout.addWidget(self.busy_bar)
        return box

    def _build_output(self) -> QGroupBox:
        box = QGroupBox("After selection... save output:")
        layout = QVBoxLayout(box)
        self.save_selected_button = QPushButton("Save Selected…")
        self.save_selected_button.setEnabled(False)
        self.save_remaining_button = QPushButton("Save Remaining…")
        self.save_remaining_button.setEnabled(False)
        layout.addLayout(_row(self.save_selected_button, self.save_remaining_button))
        return box

    def _connect_signals(self) -> None:
        """Connected last, so nothing fires at a session that is not attached yet."""
        self.features_button.clicked.connect(self.choose_features_file)
        self.people_button.clicked.connect(self.choose_people_file)
        self.panel_size_spin.valueChanged.connect(self._panel_size_changed)
        self.run_button.clicked.connect(self.run_selection)
        self.run_test_button.clicked.connect(self.run_test_selection)
        self.save_selected_button.clicked.connect(self.choose_selected_save_path)
        self.save_remaining_button.clicked.connect(self.choose_remaining_save_path)

    @property
    def session(self) -> "CsvSession":
        assert self._session is not None, "the tab needs a session before it can be used"
        return self._session

    @session.setter
    def session(self, session: "CsvSession") -> None:
        self._session = session

    def run_selection(self) -> None:
        self.session.run_selection(test_selection=False)

    def run_test_selection(self) -> None:
        self.session.run_selection(test_selection=True)

    ####################################
    # user actions - dialogs and files
    ####################################

    def choose_features_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select the categories CSV file", "", CSV_FILE_FILTER)
        if path:
            self.load_features_file(Path(path))

    def choose_people_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select the people CSV file", "", CSV_FILE_FILTER)
        if path:
            self.load_people_file(Path(path))

    def load_features_file(self, path: Path) -> None:
        self.features_label.setText(path.name)
        self.session.add_feature_content(_read_csv(path))

    def load_people_file(self, path: Path) -> None:
        self.people_label.setText(path.name)
        self.session.add_people_content(_read_csv(path))

    def choose_selected_save_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save the selected people", self._selected_filename, CSV_FILE_FILTER
        )
        if path:
            self.write_selected(Path(path))

    def choose_remaining_save_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save the remaining people", self._remaining_filename, CSV_FILE_FILTER
        )
        if path:
            self.write_remaining(Path(path))

    def write_selected(self, path: Path) -> None:
        _write_csv(path, self._selected_contents)

    def write_remaining(self, path: Path) -> None:
        _write_csv(path, self._remaining_contents)

    def _panel_size_changed(self, size: int) -> None:
        self.session.set_panel_size(size)

    ##########################
    # the CsvView protocol
    ##########################

    def set_busy(self, busy: bool) -> None:
        """Show that work is in flight, and refuse to start a second lot of it."""
        self.busy_bar.setVisible(busy)
        if busy:
            self._run_enabled_before_busy = self.run_button.isEnabled()
            self.set_run_enabled(enabled=False)
        else:
            self.set_run_enabled(enabled=self._run_enabled_before_busy)

    def set_people_input_enabled(self, enabled: bool) -> None:
        self.people_button.setEnabled(enabled)

    def set_panel_size_range(self, minimum: int, maximum: int) -> None:
        self.panel_size_spin.setRange(minimum, maximum)
        self.panel_size_label.setText(_panel_size_label(minimum, maximum))

    def set_panel_size(self, size: int) -> None:
        self.panel_size_spin.setValue(size)

    def set_run_enabled(self, enabled: bool) -> None:
        self.run_button.setEnabled(enabled)
        self.run_test_button.setEnabled(enabled)

    def offer_selected(self, contents: str, filename: str) -> None:
        self._selected_contents = contents
        self._selected_filename = filename
        self.save_selected_button.setEnabled(True)

    def offer_remaining(self, contents: str, filename: str) -> None:
        self._remaining_contents = contents
        self._remaining_filename = filename
        self.save_remaining_button.setEnabled(True)


def _row(*widgets: QWidget) -> QHBoxLayout:
    layout = QHBoxLayout()
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch()
    return layout


def _panel_size_label(minimum: int, maximum: int) -> str:
    """Once we know the range, say what it is - as the old page did."""
    if maximum <= 0:
        return PANEL_SIZE_LABEL
    return f"Step 3: {PANEL_SIZE_LABEL} ({minimum}-{maximum})"


def _read_csv(path: Path) -> str:
    # utf-8-sig so a byte order mark from a spreadsheet export does not end up glued
    # to the name of the first column
    return path.read_text(encoding="utf-8-sig")


def _write_csv(path: Path, contents: str) -> None:
    # the library writes its own line endings, so ask for no translation on the way out
    path.write_text(contents, encoding="utf-8", newline="")
