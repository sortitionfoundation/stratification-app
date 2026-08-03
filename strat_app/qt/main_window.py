# ABOUTME: The application window - the two tabs, the shared detailed log, and the wiring.
# ABOUTME: This is where sessions meet the widgets that display them.

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from strat_app.qt.csv_tab import CsvTab
from strat_app.qt.gsheet_tab import GSheetTab
from strat_app.qt.log_panel import LogDisplay, LogPanel
from strat_app.qt.workers import QtTaskRunner, QueuedLogView
from strat_app.sessions.csv_session import CsvSession
from strat_app.sessions.gsheet_session import GSheetSession
from strat_app.sessions.log import GuiLog
from strat_app.sessions.view import LogSection
from strat_app.settings_holder import DEFAULT_SETTINGS_PATH, SettingsHolder

WINDOW_TITLE = "Sortition Foundation - Stratification & Selection"
CSV_TAB_INDEX = 0
GSHEET_TAB_INDEX = 1
CSV_TAB_TITLE = "CSV file input & output"
GSHEET_TAB_TITLE = "Google Sheet input & output"
LOGO_PATH = Path(__file__).parent.parent / "resources" / "logo_sortition-foundation_alt.svg"
LOGO_HEIGHT = 50
DEFAULT_SIZE = (800, 800)


def _scrollable(widget: QWidget) -> QScrollArea:
    """
    Let a tab scroll rather than squash its contents.

    The old UI was a web page, so it scrolled when it ran out of room. Without this a
    short window silently overlaps the rows of the advanced settings.
    """
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(widget)
    return area


def tab_title(title: str) -> str:
    """
    Escape a tab title for Qt.

    Qt reads a single ampersand as marking the next letter as a keyboard shortcut, and
    swallows it. Both of our titles contain one, so both need doubling up.
    """
    return title.replace("&", "&&")


class MainWindow(QMainWindow):
    def __init__(self, settings_path: Path = DEFAULT_SETTINGS_PATH) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(*DEFAULT_SIZE)

        self.csv_tab = CsvTab()
        self.gsheet_tab = GSheetTab()
        self.log_panel = LogPanel()

        self.tabs = QTabWidget()
        self.tabs.addTab(_scrollable(self.csv_tab), tab_title(CSV_TAB_TITLE))
        self.tabs.addTab(_scrollable(self.gsheet_tab), tab_title(GSHEET_TAB_TITLE))
        # the old page opened on the Google Sheet tab
        self.tabs.setCurrentIndex(GSHEET_TAB_INDEX)

        # a splitter so the user can decide how much room the log gets
        body = QSplitter(Qt.Orientation.Vertical)
        body.addWidget(self.tabs)
        body.addWidget(self.log_panel)
        body.setStretchFactor(0, 3)
        body.setStretchFactor(1, 1)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(self._build_header())
        layout.addWidget(body)
        self.setCentralWidget(central)

        # the log is written to from worker threads, so it goes through a queued view
        self.gui_log = GuiLog(QueuedLogView(self._build_log_display()))
        self.task_runner = QtTaskRunner()
        settings_holder = SettingsHolder(settings_path)
        self.csv_tab.session = CsvSession(self.csv_tab, self.gui_log, settings_holder, runner=self.task_runner)
        self.gsheet_tab.session = GSheetSession(self.gsheet_tab, self.gui_log, settings_holder, runner=self.task_runner)

    def append_detailed_log(self, line: str) -> None:
        """Where the library's live log lines land while a selection is running."""
        self.gui_log.add(LogSection.DETAILED_LOG, line)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Let any work in flight finish rather than killing its thread."""
        self.task_runner.wait()
        super().closeEvent(event)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.addWidget(QLabel(f"<h1>{WINDOW_TITLE}</h1>"))
        header.addStretch()
        if LOGO_PATH.is_file():
            logo = QSvgWidget(str(LOGO_PATH))
            size = logo.sizeHint()
            logo.setFixedSize(LOGO_HEIGHT * size.width() // size.height(), LOGO_HEIGHT)
            header.addWidget(logo)
        return header

    def _build_log_display(self) -> LogDisplay:
        return LogDisplay(
            {
                LogSection.CSV_FEATURES: self.csv_tab.features_output,
                LogSection.CSV_SELECTION: self.csv_tab.people_output,
                LogSection.GSHEET_FEATURES: self.gsheet_tab.features_output,
                LogSection.GSHEET_SELECTION: self.gsheet_tab.people_output,
                LogSection.DETAILED_LOG: self.log_panel.browser,
            }
        )
