# ABOUTME: Renders the session layer's log entries into a Qt rich text widget.
# ABOUTME: The library's report HTML goes in here and nowhere else, so it can be swapped out.

import html
from collections.abc import Sequence

from PySide6.QtWidgets import QTextBrowser

from strat_app.sessions.view import LogEntry

MINIMUM_HEIGHT = 120


def entries_as_html(entries: Sequence[LogEntry], *, include_logged: bool = True) -> str:
    """
    Render log entries as the small subset of HTML that Qt's rich text engine handles.

    Plain text is escaped; reports are rendered by the library, which gives us bold,
    red for the critical lines, and tables. No browser and no JS is involved - this is
    Qt's own rich text, not a web page.

    `include_logged` is for the detailed log. The library both logs its progress lines
    and puts them in the report, so an area that is already showing the live log would
    otherwise show every one of them twice.
    """
    parts = [
        html.escape(entry) if isinstance(entry, str) else entry.as_html(include_logged=include_logged)
        for entry in entries
    ]
    return "<br />".join(part for part in parts if part.strip())


class ReportBrowser(QTextBrowser):
    """A read-only area showing whatever the session layer has to say."""

    def __init__(self, *, include_logged: bool = True) -> None:
        super().__init__()
        self.setMinimumHeight(MINIMUM_HEIGHT)
        self.include_logged = include_logged

    def show_entries(self, entries: Sequence[LogEntry]) -> None:
        self.setHtml(entries_as_html(entries, include_logged=self.include_logged))
