# ABOUTME: Unit tests for loading the settings TOML once and reporting problems with it.
# ABOUTME: Every path here is one the user hits on a fresh machine or a fat-fingered edit.

from pathlib import Path

from strat_app.sessions.log import GuiLog
from strat_app.sessions.view import LogSection
from strat_app.settings_holder import SettingsHolder
from tests.fakes import RecordingLogView


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
