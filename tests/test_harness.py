# ABOUTME: Smoke tests for the test harness itself - fixtures on disk, Qt able to start.
# ABOUTME: These fail loudly if the headless Qt setup breaks in CI, before any real test runs.

from pathlib import Path

from PySide6.QtWidgets import QLabel

from tests.conftest import CATEGORIES_CSV, PEOPLE_CSV


def test_fixtures_are_present() -> None:
    assert Path(CATEGORIES_CSV).is_file()
    assert Path(PEOPLE_CSV).is_file()


def test_qtbot_can_make_a_widget(qtbot) -> None:
    label = QLabel("hello")
    qtbot.addWidget(label)
    assert label.text() == "hello"
