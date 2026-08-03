# ABOUTME: Tests for rendering log entries into a Qt rich text widget.
# ABOUTME: This is the one place the library's HTML is used, so it is the one place tested for it.

from sortition_algorithms.utils import ReportLevel, RunReport
from sortition_algorithms.utils import RunReport as Report

from strat_app.qt.report_view import ReportBrowser, entries_as_html


def test_plain_text_entries_are_escaped() -> None:
    assert entries_as_html(["1 < 2 & 3 > 2"]) == "1 &lt; 2 &amp; 3 &gt; 2"


def test_blank_entries_are_dropped() -> None:
    assert entries_as_html(["first", "", "   ", "second"]) == "first<br />second"


def test_reports_are_rendered_by_the_library() -> None:
    report = RunReport()
    report.add_line("a line")

    assert entries_as_html([report]) == report.as_html()


def test_a_report_table_reaches_the_widget(qtbot) -> None:
    report = Report()
    report.add_table(["name", "count"], [["Female", 12]])
    browser = ReportBrowser()
    qtbot.addWidget(browser)

    browser.show_entries([report])

    shown = browser.toPlainText()
    assert "Female" in shown
    assert "12" in shown


def test_a_critical_line_reaches_the_widget_in_red(qtbot) -> None:
    """Infeasible targets are flagged in red, which is the whole reason for the rich text."""
    report = Report()
    report.add_line("Failed to find a panel", level=ReportLevel.CRITICAL)
    browser = ReportBrowser()
    qtbot.addWidget(browser)

    browser.show_entries([report])

    assert "Failed to find a panel" in browser.toPlainText()
    # Qt has parsed the library's `color: red` and stored it as its own colour
    assert "#ff0000" in browser.toHtml()


def test_showing_entries_replaces_what_was_there(qtbot) -> None:
    browser = ReportBrowser()
    qtbot.addWidget(browser)
    browser.show_entries(["old news"])

    browser.show_entries(["new news"])

    assert "old news" not in browser.toPlainText()
    assert "new news" in browser.toPlainText()


def test_the_browser_is_read_only(qtbot) -> None:
    browser = ReportBrowser()
    qtbot.addWidget(browser)

    assert browser.isReadOnly()
