# ABOUTME: Renders the session layer's log entries into a Qt rich text widget.
# ABOUTME: The library's report HTML goes in here and nowhere else, so it can be swapped out.

import html
from collections.abc import Sequence

from PySide6.QtWidgets import QTextBrowser

from strat_app.sessions.view import LogEntry

MINIMUM_HEIGHT = 120


def entries_as_html(entries: Sequence[LogEntry]) -> str:
    """
    Render log entries as the small subset of HTML that Qt's rich text engine handles.

    Plain text is escaped; reports are rendered by the library, which gives us bold,
    red for the critical lines, and tables. No browser and no JS is involved - this is
    Qt's own rich text, not a web page.
    """
    parts = [html.escape(entry) if isinstance(entry, str) else entry.as_html() for entry in entries]
    return "<br />".join(part for part in parts if part.strip())


class ReportBrowser(QTextBrowser):
    """A read-only area showing whatever the session layer has to say."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(MINIMUM_HEIGHT)

    def show_entries(self, entries: Sequence[LogEntry]) -> None:
        self.setHtml(entries_as_html(entries))
