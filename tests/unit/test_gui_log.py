# ABOUTME: Unit tests for the accumulating log that feeds the app's output areas.
# ABOUTME: Sections must not leak into each other, and a reset must really reset.

from sortition_algorithms.utils import RunReport

from strat_app.sessions.log import GuiLog
from strat_app.sessions.view import LogSection
from tests.fakes import RecordingLogView


def test_entries_accumulate_in_the_section_they_were_added_to() -> None:
    log_view = RecordingLogView()
    gui_log = GuiLog(log_view)

    gui_log.add(LogSection.CSV_FEATURES, "first")
    gui_log.add(LogSection.CSV_FEATURES, "second")

    assert log_view.text(LogSection.CSV_FEATURES) == "first\nsecond"
    assert log_view.text(LogSection.CSV_SELECTION) == ""


def test_adding_several_entries_at_once() -> None:
    log_view = RecordingLogView()
    gui_log = GuiLog(log_view)

    gui_log.add_all(LogSection.DETAILED_LOG, ["one", "two"])

    assert log_view.text(LogSection.DETAILED_LOG) == "one\ntwo"


def test_resetting_a_section_empties_it() -> None:
    log_view = RecordingLogView()
    gui_log = GuiLog(log_view)
    gui_log.add(LogSection.DETAILED_LOG, "old news")

    gui_log.reset(LogSection.DETAILED_LOG)

    assert log_view.text(LogSection.DETAILED_LOG) == ""


def test_resetting_a_section_can_leave_a_message_behind() -> None:
    log_view = RecordingLogView()
    gui_log = GuiLog(log_view)
    gui_log.add(LogSection.DETAILED_LOG, "old news")

    gui_log.reset(LogSection.DETAILED_LOG, "Selecting... please wait...")

    assert log_view.text(LogSection.DETAILED_LOG) == "Selecting... please wait..."


def test_reports_are_kept_as_reports_so_the_view_can_render_them() -> None:
    log_view = RecordingLogView()
    gui_log = GuiLog(log_view)
    report = RunReport()
    report.add_line("something happened")

    gui_log.add(LogSection.CSV_FEATURES, report)

    assert log_view.entries(LogSection.CSV_FEATURES) == [report]
    assert "something happened" in log_view.text(LogSection.CSV_FEATURES)


def test_updating_all_areas_pushes_every_section() -> None:
    log_view = RecordingLogView()
    gui_log = GuiLog(log_view)
    gui_log.entries[LogSection.CSV_FEATURES] = ["set behind the view's back"]

    gui_log.update_all_areas()

    assert log_view.text(LogSection.CSV_FEATURES) == "set behind the view's back"
