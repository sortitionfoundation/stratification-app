# ABOUTME: The Google Sheet tab - name a spreadsheet, load it, run a selection, write tabs back.
# ABOUTME: Implements GSheetView; the advanced settings live in a collapsible group box.

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from strat_app.qt.report_view import ReportBrowser

if TYPE_CHECKING:
    from strat_app.sessions.gsheet_session import GSheetSession

PANEL_SIZE_LABEL = "Specify the number of people to select"
RELOAD_HINT = 'If you change this, then you must click "Load G-Sheet" afterwards.'
MAX_SELECTIONS = 1000


class GSheetTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._session: GSheetSession | None = None
        self._run_enabled_before_busy = False
        self._test_run_enabled_before_busy = False
        self._load_enabled_before_busy = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Option B: Google Sheet input and output</h2>"))
        layout.addWidget(self._build_sheet_input())
        layout.addWidget(self._build_advanced_settings())
        layout.addLayout(_row(self.load_button))
        layout.addWidget(self._build_information())
        layout.addWidget(self._build_selection())
        layout.addStretch()

        self._connect_signals()

    ###############
    # the widgets
    ###############

    def _build_sheet_input(self) -> QGroupBox:
        box = QGroupBox()
        layout = QVBoxLayout(box)
        layout.addWidget(QLabel("Google spreadsheet name:"))
        self.sheet_name_edit = QLineEdit()
        layout.addWidget(self.sheet_name_edit)
        layout.addWidget(_hint(RELOAD_HINT))
        self.load_button = QPushButton("Load G-Sheet")
        self.load_button.setEnabled(False)
        return box

    def _build_advanced_settings(self) -> QGroupBox:
        box = QGroupBox("Advanced settings")
        box.setCheckable(True)
        box.setChecked(False)
        self.advanced_settings = box
        # the rows go in a widget of their own so that hiding them collapses the box,
        # rather than leaving an empty strip where they used to be
        self.advanced_contents = QWidget()
        outer = QVBoxLayout(box)
        outer.addWidget(self.advanced_contents)
        layout = QFormLayout(self.advanced_contents)

        self.people_tab_edit = QLineEdit("Respondents")
        layout.addRow("Google spreadsheet respondents tab:", self.people_tab_edit)
        layout.addRow("", _hint(RELOAD_HINT))

        self.features_tab_edit = QLineEdit("Categories")
        layout.addRow("Google spreadsheet categories tab:", self.features_tab_edit)
        layout.addRow("", _hint(RELOAD_HINT))

        self.gen_rem_tab_check = QCheckBox("Generate remaining tab")
        self.gen_rem_tab_check.setChecked(True)
        layout.addRow(self.gen_rem_tab_check)
        layout.addRow(
            "",
            _hint(
                "If this is checked then the remaining tab will be written to your sheet. "
                'If you change the check box, then you must click "Load G-Sheet" afterwards.'
            ),
        )

        self.number_selections_spin = QSpinBox()
        self.number_selections_spin.setRange(1, MAX_SELECTIONS)
        layout.addRow("Number of selections needed:", self.number_selections_spin)
        layout.addRow("", _hint(RELOAD_HINT))

        self.advanced_contents.setVisible(False)
        box.toggled.connect(self.advanced_contents.setVisible)
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
        self.set_test_run_enabled(enabled=False)
        layout.addLayout(_row(self.run_button, self.run_test_button))
        self.busy_bar = QProgressBar()
        # no phases or percentages from the library at this version, so all we can
        # honestly show is that something is happening
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setVisible(False)
        layout.addWidget(self.busy_bar)
        return box

    def _connect_signals(self) -> None:
        """Connected last, so nothing fires at a session that is not attached yet."""
        self.sheet_name_edit.textChanged.connect(self._sheet_name_changed)
        self.people_tab_edit.textChanged.connect(self._people_tab_name_changed)
        self.features_tab_edit.textChanged.connect(self._features_tab_name_changed)
        self.gen_rem_tab_check.toggled.connect(self._gen_rem_tab_toggled)
        self.number_selections_spin.valueChanged.connect(self._number_selections_changed)
        self.load_button.clicked.connect(self.load_g_sheet)
        self.panel_size_spin.valueChanged.connect(self._panel_size_changed)
        self.run_button.clicked.connect(self.run_selection)
        self.run_test_button.clicked.connect(self.run_test_selection)

    @property
    def session(self) -> "GSheetSession":
        assert self._session is not None, "the tab needs a session before it can be used"
        return self._session

    @session.setter
    def session(self, session: "GSheetSession") -> None:
        self._session = session

    ####################################
    # user actions reaching the session
    ####################################

    def _sheet_name_changed(self, text: str) -> None:
        self.session.update_g_sheet_name(text)

    def _people_tab_name_changed(self, text: str) -> None:
        self.session.update_people_tab_name(text)

    def _features_tab_name_changed(self, text: str) -> None:
        self.session.update_features_tab_name(text)

    def _gen_rem_tab_toggled(self, checked: bool) -> None:
        self.session.update_gen_rem_tab(gen_rem_tab=checked)

    def _number_selections_changed(self, value: int) -> None:
        self.session.set_number_selections(value)

    def _panel_size_changed(self, size: int) -> None:
        self.session.set_panel_size(size)

    def load_g_sheet(self) -> None:
        self.session.load_g_sheet()

    def run_selection(self) -> None:
        self.session.run_selection(test_selection=False)

    def run_test_selection(self) -> None:
        self.session.run_selection(test_selection=True)

    ###########################
    # the GSheetView protocol
    ###########################

    def set_busy(self, busy: bool) -> None:
        """Show that work is in flight, and refuse to start a second lot of it."""
        self.busy_bar.setVisible(busy)
        if busy:
            self._run_enabled_before_busy = self.run_button.isEnabled()
            self._test_run_enabled_before_busy = self.run_test_button.isEnabled()
            self._load_enabled_before_busy = self.load_button.isEnabled()
            self.set_run_enabled(enabled=False)
            self.set_test_run_enabled(enabled=False)
            self.set_load_enabled(enabled=False)
        else:
            self.set_run_enabled(enabled=self._run_enabled_before_busy)
            self.set_test_run_enabled(enabled=self._test_run_enabled_before_busy)
            self.set_load_enabled(enabled=self._load_enabled_before_busy)

    def set_load_enabled(self, enabled: bool) -> None:
        self.load_button.setEnabled(enabled)

    def set_panel_size_range(self, minimum: int, maximum: int) -> None:
        self.panel_size_spin.setRange(minimum, maximum)
        self.panel_size_label.setText(_panel_size_label(minimum, maximum))

    def set_panel_size(self, size: int) -> None:
        self.panel_size_spin.setValue(size)

    def set_run_enabled(self, enabled: bool) -> None:
        self.run_button.setEnabled(enabled)

    def set_test_run_enabled(self, enabled: bool) -> None:
        self.run_test_button.setEnabled(enabled)


def _row(*widgets: QWidget) -> QHBoxLayout:
    layout = QHBoxLayout()
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch()
    return layout


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setEnabled(False)  # greyed out, as the old page's muted help text was
    return label


def _panel_size_label(minimum: int, maximum: int) -> str:
    """Once we know the range, say what it is - as the old page did."""
    if maximum <= 0:
        return PANEL_SIZE_LABEL
    return f"Step 3: {PANEL_SIZE_LABEL} ({minimum}-{maximum})"
