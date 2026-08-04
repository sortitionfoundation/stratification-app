# ABOUTME: Loads the user's settings TOML once and remembers whether it worked.
# ABOUTME: Reports problems into a log section so they surface early, next to the user's action.

from pathlib import Path

from sortition_algorithms import Settings

from strat_app.sessions.log import GuiLog
from strat_app.sessions.view import LogSection

DEFAULT_SETTINGS_PATH = Path.home() / "sf_stratification_settings.toml"

# The library accepts more than this app ships. python-mip is left out of the packaged
# build because it brings 275MB of CBC with it, and diversimax needs pandas and
# scikit-learn, which we do not install. Both are settings a user can write down and
# neither fails until a run is well under way, so we refuse them at load time instead.
SUPPORTED_SOLVER_BACKENDS = ("highspy",)
SUPPORTED_SELECTION_ALGORITHMS = ("legacy", "maximin", "nash", "leximin")


def unsupported_message(settings: Settings) -> str:
    """
    Say what in these settings this build cannot honour, or nothing if it can honour it all.

    Deliberately a refusal rather than a quiet substitution. Swapping the user's solver
    or algorithm for a working one would have two machines with the same settings file
    selecting panels by different methods without saying so.
    """
    problems = [
        _unsupported("solver_backend", settings.solver_backend, SUPPORTED_SOLVER_BACKENDS),
        _unsupported("selection_algorithm", settings.selection_algorithm, SUPPORTED_SELECTION_ALGORITHMS),
    ]
    return "\n".join(problem for problem in problems if problem)


def _unsupported(name: str, value: str, supported: tuple[str, ...]) -> str:
    if value in supported:
        return ""
    return (
        f"The {name} '{value}' is not available in this build. "
        f"Edit {name} in your settings file to one of: {', '.join(supported)} - "
        f"then restart this app."
    )


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
                settings, report = Settings.load_from_file(settings_file_path=self.settings_path)
            except Exception as error:
                return f"Error reading in settings file: {error}"
            unsupported = unsupported_message(settings)
            if unsupported:
                return unsupported
            self._settings = settings
            return report.as_text()
        return ""

    def init_settings_log(self, gui_log: GuiLog, section: LogSection) -> None:
        message = self.init_settings()
        if message:
            gui_log.add(section, message)

    def loaded(self) -> bool:
        return self._settings is not None
