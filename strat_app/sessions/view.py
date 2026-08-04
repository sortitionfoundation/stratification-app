# ABOUTME: The protocols the session layer uses to talk to whatever is displaying it.
# ABOUTME: Deliberately free of any UI library, so the sessions can be tested without one.

from collections.abc import Sequence
from enum import Enum
from typing import Protocol

from sortition_algorithms.utils import RunReport


class LogSection(Enum):
    """The output areas of the app that accumulate messages."""

    CSV_FEATURES = 1
    CSV_SELECTION = 2
    GSHEET_FEATURES = 3
    GSHEET_SELECTION = 4
    DETAILED_LOG = 5


# A line of plain text, or a report from the sortition-algorithms library. The view
# decides how to render each; the session layer never produces markup.
LogEntry = str | RunReport


class LogView(Protocol):
    def show_log(self, section: LogSection, entries: Sequence[LogEntry]) -> None: ...


class CsvView(Protocol):
    def set_busy(self, busy: bool) -> None: ...

    def set_people_input_enabled(self, enabled: bool) -> None: ...

    def set_panel_size_range(self, minimum: int, maximum: int) -> None: ...

    def set_panel_size(self, size: int) -> None: ...

    def set_run_enabled(self, enabled: bool) -> None: ...

    def offer_selected(self, contents: str, filename: str) -> None: ...

    def offer_remaining(self, contents: str, filename: str) -> None: ...


class GSheetView(Protocol):
    def set_busy(self, busy: bool) -> None: ...

    def set_load_enabled(self, enabled: bool) -> None: ...

    def set_panel_size_range(self, minimum: int, maximum: int) -> None: ...

    def set_panel_size(self, size: int) -> None: ...

    def set_run_enabled(self, enabled: bool) -> None: ...

    def set_test_run_enabled(self, enabled: bool) -> None: ...
