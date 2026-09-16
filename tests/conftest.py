# ABOUTME: Shared pytest fixtures and settings that every test in the suite relies on.
# ABOUTME: Also forces Qt to the offscreen platform so the suite runs headless.

import os
from pathlib import Path

import pytest

# Must happen before anything imports QtGui, so it lives at module level rather than
# in a fixture. setdefault means you can still run with a real window if you want to.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FIXTURE_DIR = Path(__file__).parent / "fixtures"
CATEGORIES_CSV = FIXTURE_DIR / "categories_no_flex.csv"
PEOPLE_CSV = FIXTURE_DIR / "people.csv"
PEOPLE_TOO_FEW_CSV = FIXTURE_DIR / "people_too_few.csv"

# The first thing the library logs once a selection is properly under way, and so the
# first sign of life the detailed log can show. The default algorithm is maximin; pick
# a different one in the settings and this line changes with it.
ALGORITHM_LINE = "Using maximin algorithm."


@pytest.fixture
def categories_contents() -> str:
    return CATEGORIES_CSV.read_text()


@pytest.fixture
def people_contents() -> str:
    return PEOPLE_CSV.read_text()


@pytest.fixture
def people_too_few_contents() -> str:
    return PEOPLE_TOO_FEW_CSV.read_text()


@pytest.fixture
def settings_path(tmp_path: Path) -> Path:
    """
    A path for the settings TOML file, inside tmp_path.

    The file does not exist, so `Settings.load_from_file()` writes the default settings
    there - which is what the app does on a machine that has never run it before.
    """
    return tmp_path / "sf_stratification_settings.toml"
