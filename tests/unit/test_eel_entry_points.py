# ABOUTME: Tests for the eel entry point layer that still wraps the session layer.
# ABOUTME: Temporary - this file goes when script.py and the eel views do.

from typing import TYPE_CHECKING

import pytest
from sortition_algorithms.utils import RunReport

import script
from eel_views import EelCsvView, EelGSheetView, EelLogView, entries_as_html

if TYPE_CHECKING:
    from strat_app.sessions.view import CsvView, GSheetView, LogView


@pytest.mark.parametrize(
    ("typed", "expected"),
    [("22", 22), (" 22 ", 22), ("", 0), ("nonsense", 0), ("-5", 0), ("0", 0)],
)
def test_panel_size_from_a_free_text_box(typed: str, expected: int) -> None:
    """The browser UI lets the user type anything, so anything has to be survivable."""
    assert script.panel_size_from_input(typed) == expected


def test_plain_text_entries_are_escaped() -> None:
    assert entries_as_html(["1 < 2 & 3 > 2"]) == "1 &lt; 2 &amp; 3 &gt; 2"


def test_blank_entries_are_dropped() -> None:
    assert entries_as_html(["first", "", "   ", "second"]) == "first<br />second"


def test_reports_are_rendered_by_the_library() -> None:
    report = RunReport()
    report.add_line("a line")

    assert entries_as_html([report]) == report.as_html()


def test_the_eel_views_satisfy_the_view_protocols() -> None:
    """The annotations are the test - mypy checks each adapter against its protocol."""
    csv_view: CsvView = EelCsvView()
    g_sheet_view: GSheetView = EelGSheetView()
    log_view: LogView = EelLogView()

    assert csv_view is not None
    assert g_sheet_view is not None
    assert log_view is not None
