# ABOUTME: Loads the user's settings TOML once and remembers whether it worked.
# ABOUTME: Reports problems into a log section so they surface early, next to the user's action.

from pathlib import Path

from sortition_algorithms import Settings

from strat_app.sessions.log import GuiLog
from strat_app.sessions.view import LogSection

DEFAULT_SETTINGS_PATH = Path.home() / "sf_stratification_settings.toml"


class SettingsHolder:
    def __init__(self, settings_path: Path = DEFAULT_SETTINGS_PATH) -> None:
        self.settings_path = settings_path
        self._settings: Settings | None = None

    @property
    def settings(self) -> Settings:
        self.init_settings()
        assert self._settings is not None
        return self._settings

    def init_settings(self) -> str:
        """
        Load the settings if they are not loaded yet.

        Called from lots of places to report the error early. Returns a message to show
        the user, or an empty string when there is nothing to say.
        """
        if self._settings is None:
            try:
                self._settings, report = Settings.load_from_file(settings_file_path=self.settings_path)
                return report.as_text()
            except Exception as error:
                return f"Error reading in settings file: {error}"
        return ""

    def init_settings_log(self, gui_log: GuiLog, section: LogSection) -> None:
        message = self.init_settings()
        if message:
            gui_log.add(section, message)

    def loaded(self) -> bool:
        return self._settings is not None
