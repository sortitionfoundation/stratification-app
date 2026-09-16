# ABOUTME: Tests the app entry point, including the --self-test flag CI runs against a build.
# ABOUTME: The classic PySide6 packaging failure only ever shows up in the packaged artefact.

import subprocess
import sys

import main as pyinstaller_entry_point
from strat_app.__main__ import main, parse_args

SELF_TEST_TIMEOUT_S = 120


def test_the_self_test_flag_is_off_by_default() -> None:
    assert parse_args([]).self_test is False


def test_the_self_test_flag_is_recognised() -> None:
    assert parse_args(["--self-test"]).self_test is True


def test_the_app_builds_and_exits_cleanly() -> None:
    """
    Run it as a subprocess, because it makes a QApplication of its own.

    This is the same call the packaged binary gets in CI - if Qt cannot find its
    platform plugin, this is where it says so.
    """
    result = subprocess.run(
        [sys.executable, "-m", "strat_app", "--self-test"],
        capture_output=True,
        text=True,
        timeout=SELF_TEST_TIMEOUT_S,
        check=False,
    )

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


def test_main_is_importable_from_the_pyinstaller_entry_point() -> None:
    """main.py is what PyInstaller builds; it must keep pointing at the real thing."""
    assert pyinstaller_entry_point.main is main
