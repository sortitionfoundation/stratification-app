# ABOUTME: Implements the view protocols against the old eel/browser UI.
# ABOUTME: Temporary - it keeps the eel app running during the Qt port, and dies with it.

import html
from collections.abc import Sequence

import eel

from strat_app.sessions.view import LogEntry, LogSection

LOG_SECTION_JS_FUNCTIONS = {
    LogSection.CSV_FEATURES: "update_csv_features_output_area",
    LogSection.CSV_SELECTION: "update_csv_selection_output_area",
    LogSection.GSHEET_FEATURES: "update_g_sheet_features_output_area",
    LogSection.GSHEET_SELECTION: "update_g_sheet_selection_output_area",
    LogSection.DETAILED_LOG: "update_detailed_log_messages_area",
}


def entries_as_html(entries: Sequence[LogEntry]) -> str:
    """Render log entries as the HTML the browser UI expects, skipping blank ones."""
    parts = [html.escape(entry) if isinstance(entry, str) else entry.as_html() for entry in entries]
    return "<br />".join(part for part in parts if part.strip())


def call_js(function_name: str, *args: object) -> None:
    """
    Call an eel-exposed JS function by name.

    By name because eel only grows the attribute once the browser has registered the
    function, so looking them up ahead of time would fail.
    """
    getattr(eel, function_name)(*args)


class EelLogView:
    def show_log(self, section: LogSection, entries: Sequence[LogEntry]) -> None:
        call_js(LOG_SECTION_JS_FUNCTIONS[section], entries_as_html(entries))


class EelCsvView:
    def set_busy(self, busy: bool) -> None:
        """The old page has nowhere to show this, and nothing runs off-thread in it."""

    def set_people_input_enabled(self, enabled: bool) -> None:
        if enabled:
            call_js("enable_csv_selection_content")

    def set_panel_size_range(self, minimum: int, maximum: int) -> None:
        call_js("update_csv_selection_range", minimum, maximum)

    def set_panel_size(self, size: int) -> None:
        # the old UI shows an empty box rather than a zero when nothing is set
        call_js("set_csv_panel_size", str(size) if size else "")

    def set_run_enabled(self, enabled: bool) -> None:
        call_js("enable_csv_run_button" if enabled else "disable_csv_run_button")

    def offer_selected(self, contents: str, filename: str) -> None:
        call_js("enable_csv_selected_download", contents, filename)

    def offer_remaining(self, contents: str, filename: str) -> None:
        call_js("enable_csv_remaining_download", contents, filename)


class EelGSheetView:
    def set_busy(self, busy: bool) -> None:
        """The old page has nowhere to show this, and nothing runs off-thread in it."""

    def set_load_enabled(self, enabled: bool) -> None:
        if enabled:
            call_js("enable_load_g_sheet_btn")

    def set_panel_size_range(self, minimum: int, maximum: int) -> None:
        call_js("update_g_sheet_selection_range", minimum, maximum)

    def set_panel_size(self, size: int) -> None:
        # the old UI shows an empty box rather than a zero when nothing is set
        call_js("set_g_sheet_panel_size", str(size) if size else "")

    def set_run_enabled(self, enabled: bool) -> None:
        call_js("enable_g_sheet_run_button" if enabled else "disable_g_sheet_run_button")
