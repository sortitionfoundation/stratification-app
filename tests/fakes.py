# ABOUTME: Test doubles used across the suite - a recorder for view calls and a fake spreadsheet.
# ABOUTME: The fake data source is backed by CSV fixtures so gsheet tests need no credentials.

from collections.abc import Generator, Iterable, Sequence
from contextlib import contextmanager
from typing import Any

from sortition_algorithms import adapters
from sortition_algorithms.utils import RunReport

from strat_app.sessions.view import LogEntry, LogSection

# what a data source yields to the library: the column headers and the rows
TabData = Generator[tuple[Iterable[str], Iterable[dict[str, str]]], None, None]


class CallRecorder:
    """
    Records every call made to it, so a test can assert on the sequence.

    Any attribute is callable and returns None, which is enough to stand in for
    both the eel module and the view protocols - all of their methods return None.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def __getattr__(self, name: str) -> Any:
        def record(*args: Any, **kwargs: Any) -> None:
            self.calls.append((name, (*args, *kwargs.values())))

        return record

    @property
    def names(self) -> list[str]:
        """The names of the calls made, in order."""
        return [name for name, _ in self.calls]

    def args_for(self, name: str) -> list[tuple[Any, ...]]:
        """The arguments of every call to `name`, in order."""
        return [args for called_name, args in self.calls if called_name == name]

    def last_args(self, name: str) -> tuple[Any, ...]:
        """The arguments of the most recent call to `name`."""
        return self.args_for(name)[-1]

    def called(self, name: str) -> bool:
        return name in self.names

    def reset(self) -> None:
        self.calls = []


class RecordingLogView:
    """
    A LogView that keeps the entries instead of displaying them.

    Tests mostly want to know "does this message appear in that output area", so it
    renders reports to plain text on request rather than storing them rendered.
    """

    def __init__(self) -> None:
        self.sections: dict[LogSection, list[LogEntry]] = {section: [] for section in LogSection}

    def show_log(self, section: LogSection, entries: Sequence[LogEntry]) -> None:
        self.sections[section] = list(entries)

    def text(self, section: LogSection) -> str:
        """Everything currently shown in a section, as plain text."""
        parts = [entry if isinstance(entry, str) else entry.as_text() for entry in self.sections[section]]
        return "\n".join(part for part in parts if part.strip())

    def entries(self, section: LogSection) -> list[LogEntry]:
        return self.sections[section]


class TabNotFoundError(Exception):
    """Raised by FakeGSheetDataSource when asked for a tab that isn't there."""


class FakeGSheetDataSource(adapters.CSVStringDataSource):
    """
    A stand-in for GSheetDataSource with the same API, backed by strings.

    The real one talks to the Google Sheets API, which we have no credentials for in
    the test suite. This gives the same surface - a spreadsheet name, named tabs, and
    output written to new tabs - without the network, so the session and widget code
    can be exercised for real.
    """

    def __init__(self, tabs: dict[str, str], sheet_names: Iterable[str] = ()) -> None:
        super().__init__("", "")
        self.tabs = tabs
        self.sheet_names = list(sheet_names)
        self.feature_tab_name = ""
        self.people_tab_name = ""
        self.already_selected_tab_name = ""
        self.selected_tab_name = ""
        self.remaining_tab_name = ""
        self.g_sheet_name = ""
        self.highlighted_dupes: list[int] | None = None

    def set_g_sheet_name(self, g_sheet_name: str) -> None:
        if self.sheet_names and g_sheet_name not in self.sheet_names:
            msg = f"Cannot find spreadsheet {g_sheet_name}"
            raise TabNotFoundError(msg)
        self.g_sheet_name = g_sheet_name

    def _tab_contents(self, tab_name: str) -> str:
        if tab_name not in self.tabs:
            msg = f"no tab called '{tab_name}' in the spreadsheet"
            raise TabNotFoundError(msg)
        return self.tabs[tab_name]

    @contextmanager
    def read_feature_data(self, report: RunReport) -> TabData:
        self.features_data = self._tab_contents(self.feature_tab_name)
        with super().read_feature_data(report) as headers_and_body:
            yield headers_and_body

    @contextmanager
    def read_people_data(self, report: RunReport) -> TabData:
        self.people_data = self._tab_contents(self.people_tab_name)
        with super().read_people_data(report) as headers_and_body:
            yield headers_and_body

    def highlight_dupes(self, dupes: list[int]) -> None:
        self.highlighted_dupes = dupes
