# ABOUTME: Accumulates the messages shown in each of the app's output areas.
# ABOUTME: Holds text and library reports as they are; rendering them is the view's job.

from collections.abc import Iterable

from strat_app.sessions.view import LogEntry, LogSection, LogView


class GuiLog:
    """
    The messages currently shown in each output area.

    Each section accumulates entries until something resets it - typically the start
    of a new load or a new selection run. Every change pushes the whole section to
    the view, which is cheap and means the view holds no state of its own.

    Slow work adds to the log as it goes, from whatever thread it is running on, so
    the view supplied here has to be safe to call from anywhere.
    """

    def __init__(self, view: LogView) -> None:
        self.view = view
        self.entries: dict[LogSection, list[LogEntry]] = {section: [] for section in LogSection}

    def reset(self, section: LogSection, first_entry: LogEntry | None = None) -> None:
        self.entries[section] = [] if first_entry is None else [first_entry]
        self.update_area(section)

    def add(self, section: LogSection, entry: LogEntry) -> None:
        self.entries[section].append(entry)
        self.update_area(section)

    def add_all(self, section: LogSection, entries: Iterable[LogEntry]) -> None:
        self.entries[section] += entries
        self.update_area(section)

    def update_area(self, section: LogSection) -> None:
        self.view.show_log(section, self.entries[section])

    def update_all_areas(self) -> None:
        for section in LogSection:
            self.update_area(section)
