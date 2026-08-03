# ABOUTME: The application entry point - builds the QApplication and shows the window.
# ABOUTME: `uv run python -m strat_app`, or the packaged binary, both end up here.

import argparse
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QApplication

from strat_app.qt.main_window import WINDOW_TITLE, MainWindow
from strat_app.qt.workers import user_log_handler
from strat_app.self_test import run_self_test

ORGANISATION = "Sortition Foundation"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="strat-select", description=WINDOW_TITLE)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="build the window, run a small selection, and exit - used to smoke test a packaged build",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName(WINDOW_TITLE)
    app.setOrganizationName(ORGANISATION)

    if args.self_test:
        # a settings file of its own, so a smoke test does not write to the user's home
        with tempfile.TemporaryDirectory() as scratch:
            window = MainWindow(settings_path=Path(scratch) / "sf_stratification_settings.toml")
            window.show()
            return run_self_test(window)

    window = MainWindow()
    # the library logs its progress as a run goes along; this is what puts those lines
    # in the detailed log rather than on a stdout that a windowed build does not have
    with user_log_handler(window.append_detailed_log):
        window.show()
        return app.exec()


if __name__ == "__main__":
    sys.exit(main())
