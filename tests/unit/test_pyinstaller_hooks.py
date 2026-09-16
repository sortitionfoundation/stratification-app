# noqa: INP001
# ABOUTME: Tests that our PyInstaller hooks stay in sync with the packages they patch.
# ABOUTME: Catches upstream renames that would silently break the frozen executables.

import importlib.util
import runpy
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parents[2] / "pyinstallerhooks"


def load_hook(name):
    """
    Return the namespace of a hook file.

    The hooks dir is not a package, so we run the file by path. We use runpy
    rather than importlib because runpy compiles the source afresh - importlib
    would happily hand us a stale __pycache__ entry.
    """
    return runpy.run_path(str(HOOKS_DIR / f"hook-{name}.py"))


def test_osqp_hook_lists_the_backend_osqp_actually_loads():
    """
    osqp resolves its algebra backend with importlib at runtime, so PyInstaller
    cannot see it. If osqp ever renames or moves the backend module, this test
    fails rather than the users' executables.
    """
    osqp_interface = pytest.importorskip("osqp.interface")
    hook = load_hook("osqp")

    backend_module = osqp_interface.default_algebra_module().__name__
    assert backend_module in hook["hiddenimports"]


def test_osqp_hook_backend_is_importable():
    """A hidden import that does not exist would be silently ignored by PyInstaller."""
    pytest.importorskip("osqp")
    hook = load_hook("osqp")

    for module_name in hook["hiddenimports"]:
        assert importlib.util.find_spec(module_name) is not None
