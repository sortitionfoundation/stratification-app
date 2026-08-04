# ABOUTME: The PyInstaller build recipe - one spec covering Linux, Windows and macOS.
# ABOUTME: Run it with `uv run pyinstaller strat-select.spec`.
# -*- mode: python ; coding: utf-8 -*-

import sys

MACOS = sys.platform == "darwin"
WINDOWS = sys.platform in ("win32", "cygwin")

NAMES = {"darwin": "strat-select-macos", "win32": "strat-select-win", "cygwin": "strat-select-win"}
NAME = NAMES.get(sys.platform, "strat-select-linux")

# Qt modules we do not use. PySide6-Essentials keeps QtWebEngine and the addons out of
# the wheel set entirely; this drops what is left over from the bundle. QtDBus and
# QtNetwork stay - the Linux platform plugin wants the first, and Qt reaches for the
# second in places that are not obvious.
EXCLUDES = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    # nothing here draws a chart or opens a notebook
    "matplotlib",
    "IPython",
    "tkinter",
    "pytest",
    # The library's default solver backend is highspy. python-mip is still one of its
    # hard dependencies, but we never ask for it - and since 1.17 it keeps CBC in a
    # separate cbcbox wheel that unpacks to 275MB, which is bigger than the rest of the
    # bundle put together. Leaving both out means find_spec("mip") comes back empty and
    # sortition_algorithms sets MIP_AVAILABLE to False, which is what we want.
    # If you ever need a mip backend, these two come out and the bundle grows a lot.
    "mip",
    "cbcbox",
]

analysis = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("strat_app/resources/*.svg", "strat_app/resources")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
    # cvxpy lists its own package directory at import time on Python 3.12+, to build a
    # list of prefixes for warnings.warn. That directory does not exist when the modules
    # live in the archive, so it has to be written out as files as well.
    module_collection_mode={"cvxpy": "pyz+py"},
)
pyz = PYZ(analysis.pure)

if MACOS:
    # onedir, because an app bundle needs one
    exe = EXE(
        pyz,
        analysis.scripts,
        [],
        exclude_binaries=True,
        name=NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        # This was pinned because python-mip had no arm64 macOS wheel. We no longer
        # bundle mip at all, and highspy ships arm64 wheels, so nothing here needs
        # x86_64 any more - an arm64 build is a change to the runner and this line,
        # and wants testing on a real ARM Mac rather than being done blind.
        target_arch="x86_64",
        codesign_identity=None,
        entitlements_file=None,
    )
    collected = COLLECT(
        exe,
        analysis.binaries,
        analysis.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=NAME,
    )
    app = BUNDLE(
        collected,
        name=f"{NAME}.app",
        icon=None,
        bundle_identifier="org.sortitionfoundation.strat-select",
    )
else:
    exe = EXE(
        pyz,
        analysis.scripts,
        analysis.binaries,
        analysis.datas,
        [],
        name=NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=not WINDOWS,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
