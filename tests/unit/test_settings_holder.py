# ABOUTME: Unit tests for loading the settings TOML once and reporting problems with it.
# ABOUTME: Every path here is one the user hits on a fresh machine or a fat-fingered edit.

from pathlib import Path

import pytest

from strat_app.sessions.log import GuiLog
from strat_app.sessions.view import LogSection
from strat_app.settings_holder import SettingsHolder
from tests.fakes import RecordingLogView


def write_settings(path: Path, **overrides: str) -> Path:
    """Write the smallest settings file the library will load, plus any overrides."""
    lines = [
        'id_column = "nationbuilder_id"',
        'columns_to_keep = ["first_name"]',
        "check_same_address = false",
        *[f'{key} = "{value}"' for key, value in overrides.items()],
    ]
    path.write_text("\n".join(lines) + "\n")
    return path


def test_a_missing_settings_file_is_written_with_the_defaults(settings_path: Path) -> None:
    holder = SettingsHolder(settings_path)

    message = holder.init_settings()

    assert settings_path.is_file()
    assert "Wrote default settings" in message
    assert holder.loaded()


def test_settings_are_only_loaded_once(settings_path: Path) -> None:
    holder = SettingsHolder(settings_path)
    holder.init_settings()

    assert holder.init_settings() == ""


def test_a_broken_settings_file_is_reported_and_not_loaded(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text("id_column = ")
    holder = SettingsHolder(settings_file)

    message = holder.init_settings()

    assert "Error reading in settings file" in message
    assert not holder.loaded()


def test_a_broken_settings_file_is_reported_every_time_it_is_asked_for(tmp_path: Path) -> None:
    """Nothing is cached on failure, so the user sees the problem wherever they go next."""
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text("id_column = ")
    holder = SettingsHolder(settings_file)

    assert "Error reading in settings file" in holder.init_settings()
    assert "Error reading in settings file" in holder.init_settings()


def test_the_message_goes_into_the_log_section_asked_for(settings_path: Path) -> None:
    log = RecordingLogView()
    holder = SettingsHolder(settings_path)

    holder.init_settings_log(GuiLog(log), LogSection.GSHEET_FEATURES)

    assert "Wrote default settings" in log.text(LogSection.GSHEET_FEATURES)
    assert log.text(LogSection.CSV_FEATURES) == ""


def test_nothing_is_logged_when_there_is_nothing_to_say(settings_path: Path) -> None:
    log = RecordingLogView()
    holder = SettingsHolder(settings_path)
    holder.init_settings()

    holder.init_settings_log(GuiLog(log), LogSection.CSV_FEATURES)

    assert log.text(LogSection.CSV_FEATURES) == ""


@pytest.mark.parametrize("backend", ["mip", "mip-cbc", "mip-highs", "mip-gurobi"])
def test_a_mip_solver_backend_is_refused(tmp_path: Path, backend: str) -> None:
    """
    The mip solver is not in the build, so saying so now beats failing ten minutes in.

    python-mip keeps CBC in a 275MB wheel we deliberately leave out of the bundle, so
    these are all values the library accepts and this build cannot honour.
    """
    holder = SettingsHolder(write_settings(tmp_path / "settings.toml", solver_backend=backend))

    message = holder.init_settings()

    assert backend in message
    assert "highspy" in message
    assert not holder.loaded()


def test_the_diversimax_algorithm_is_refused(tmp_path: Path) -> None:
    """diversimax needs pandas and scikit-learn, which this app does not ship."""
    holder = SettingsHolder(write_settings(tmp_path / "settings.toml", selection_algorithm="diversimax"))

    message = holder.init_settings()

    assert "diversimax" in message
    assert not holder.loaded()


def test_the_refusal_names_the_algorithms_that_do_work(tmp_path: Path) -> None:
    holder = SettingsHolder(write_settings(tmp_path / "settings.toml", selection_algorithm="diversimax"))

    message = holder.init_settings()

    assert "maximin" in message


@pytest.mark.parametrize("algorithm", ["legacy", "maximin", "nash", "leximin"])
def test_the_algorithms_this_build_supports_are_accepted(tmp_path: Path, algorithm: str) -> None:
    holder = SettingsHolder(write_settings(tmp_path / "settings.toml", selection_algorithm=algorithm))

    assert "not available in this build" not in holder.init_settings()
    assert holder.loaded()


def test_the_highspy_backend_is_accepted(tmp_path: Path) -> None:
    holder = SettingsHolder(write_settings(tmp_path / "settings.toml", solver_backend="highspy"))

    assert "not available in this build" not in holder.init_settings()
    assert holder.loaded()


def test_the_settings_file_written_for_a_new_user_is_supported(settings_path: Path) -> None:
    """
    The library writes its own defaults on a fresh machine, so they had better pass.

    If the library ever changes DEFAULT_BACKEND to something we exclude, this is the
    test that says so before a user finds out.
    """
    holder = SettingsHolder(settings_path)

    message = holder.init_settings()

    assert "not available in this build" not in message
    assert holder.loaded()


def test_an_unsupported_setting_is_reported_every_time_it_is_asked_for(tmp_path: Path) -> None:
    """Nothing is cached on refusal, so the user sees the problem wherever they go next."""
    holder = SettingsHolder(write_settings(tmp_path / "settings.toml", solver_backend="mip"))

    assert "not available in this build" in holder.init_settings()
    assert "not available in this build" in holder.init_settings()


def test_an_unsupported_setting_is_reported_into_the_log_section(tmp_path: Path) -> None:
    log = RecordingLogView()
    holder = SettingsHolder(write_settings(tmp_path / "settings.toml", solver_backend="mip"))

    holder.init_settings_log(GuiLog(log), LogSection.CSV_FEATURES)

    assert "not available in this build" in log.text(LogSection.CSV_FEATURES)
