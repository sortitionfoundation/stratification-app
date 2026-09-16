# ABOUTME: The collapsible detailed log at the bottom of the window, and the log router.
# ABOUTME: LogDisplay is what the session layer sees as its LogView.

from collections.abc import Sequence

from PySide6.QtWidgets import QGroupBox, QVBoxLayout

from strat_app.qt.report_view import ReportBrowser
from strat_app.sessions.view import LogEntry, LogSection

DETAILED_LOG_TITLE = "Detailed Log"


class LogPanel(QGroupBox):
    """The detailed log, which the user can collapse when they are not interested."""

    def __init__(self) -> None:
        super().__init__(DETAILED_LOG_TITLE)
        self.setCheckable(True)
        self.setChecked(True)
        # the live log from the library already shows these lines as they happen
        self.browser = ReportBrowser(include_logged=False)
        layout = QVBoxLayout(self)
        layout.addWidget(self.browser)
        self.toggled.connect(self.browser.setVisible)


class LogDisplay:
    """
    Sends each log section to the output area it belongs in.

    The session layer knows only about sections; which widget shows a section is a
    decision for the window that assembled them.
    """

    def __init__(self, areas: dict[LogSection, ReportBrowser]) -> None:
        self.areas = areas

    def show_log(self, section: LogSection, entries: Sequence[LogEntry]) -> None:
        self.areas[section].show_entries(entries)
