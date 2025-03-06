Strat App
=========

[![Test Status](https://github.com/sortitionfoundation/stratification-app/workflows/tests/badge.svg?branch=master)](https://github.com/sortitionfoundation/stratification-app/actions?workflow=tests)

A simple GUI for stratification for sortition/citizens' assemblies.

About
-----

Random stratified selection software

Development
-----------

The app is built using [eel](https://github.com/ChrisKnott/Eel) - a framework that allows the GUI to be defined in HTML and CSS, but then some basic JavaScript can call Python and I can do the heavy lifting in Python.

### Install for development

First you need to have the following installed:

- git
- python 3.11 or 3.12
- a recent version of Chrome or Chromium
- `uv` - see <https://docs.astral.sh/uv/>

### Running in development

When you first set up a development version, you need to clone this repo, open a terminal in the root of the repo and run:

``` sh
uv run python script.py
```

At this point you should have a window pop up and be able to interact with it, either via uploading .csv files or else by reading directly from a google sheet.

As you update the repo or want to re-run, the above command is all you need.

### Key files

The python command *python script.py* requires only:

- script.py
- stratification.py
- all of the files in the folder *web*

To use `uv` (as we suggest above) to control dependencies, you need *pyproject.toml*

To create exectuables using pyinstaller (as we describe below), you need `hook-mip.py` to deal with [this error](https://github.com/coin-or/python-mip/issues/198).

Executables
-----------

You can download executables from the latest [releases page](https://github.com/sortitionfoundation/stratification-app/releases).  These are built by GitHub Actions.

### Manual builds

If you want to make an executable yourself, use [PyInstaller](https://pyinstaller.readthedocs.io/en/stable/).  The following set of commands, run in the root of the repo, create a single file executable in the folder `dist`.

``` sh
git pull
uv run python -m eel script.py web --additional-hooks-dir=. --onefile --noconsole
```

The resulting executable will work on any computer running the same operating system as yours, i.e. Windows, Mac OS or Linux.  So if you run the above command on Linux, you can give the file to someone else running Linux. If the person who wants the app is running Windows, you need to run the above command on Windows.
