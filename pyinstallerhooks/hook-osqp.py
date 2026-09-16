# noqa: INP001
# ABOUTME: PyInstaller hook that bundles the OSQP algebra backend extension module.
# ABOUTME: OSQP imports the backend dynamically, so PyInstaller cannot find it unaided.

# osqp picks its algebra backend at runtime with importlib.import_module() - see
# _ALGEBRA_MODULES in osqp/interface.py. PyInstaller's static analysis cannot see
# through that, so without this hook the frozen app dies on startup with
# "RuntimeError: No algebra backend available!".
#
# Only the builtin backend ships in the osqp wheels on PyPI - the osqp_cuda and
# osqp_mkl backends are separate optional packages that we do not depend on.
#
# https://github.com/orgs/osqp/discussions/657
hiddenimports = ["osqp.ext_builtin"]
