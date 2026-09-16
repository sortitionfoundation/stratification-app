Strat App
=========

[![Test Status](https://github.com/sortitionfoundation/stratification-app/actions/workflows/run-tests.yml/badge.svg?branch=main)](https://github.com/sortitionfoundation/stratification-app/actions/workflows/run-tests.yml)

A simple GUI for stratification for sortition/citizens' assemblies.

About
-----

Random stratified selection software.

The algorithms are described in [this paper (open access)](https://www.nature.com/articles/s41586-021-03788-6).

Other relevant papers:

* Procaccia et al. [Is Sortition Both Representative and Fair?](https://procaccia.info/wp-content/uploads/2022/06/repfair.pdf)
* Tiago c Peixoto
  * [Reflections on the representativeness of citizens’ assemblies and similar innovations](https://democracyspot.net/2023/02/22/reflections-on-the-representativeness-of-citizens-assemblies-and-similar-innovations/) and
  * [How representative is it really? A correspondence on sortition](https://www.publicdeliberation.net/how-representative-is-it-really-a-correspondence-on-sortition/)

Development
-----------

The GUI is built with [PySide6](https://doc.qt.io/qtforpython-6/) - native Qt widgets, in
Python. There is no HTML, no JavaScript and no embedded browser.

### Install for development

First you need to have the following installed:

- git
- python 3.11 or 3.12
- `uv` - see <https://docs.astral.sh/uv/>
- `just` - see <https://just.systems/> (optional, but the recipes below assume it)

### Running in development

When you first set up a development version, you need to clone this repo, open a terminal in the root of the repo and run:

``` sh
just run
```

At this point you should have a window pop up and be able to interact with it, either by
choosing .csv files or else by reading directly from a google sheet.

As you update the repo or want to re-run, the above command is all you need.

### Tests and checks

``` sh
just test    # unit, integration and end to end
just check   # ruff format, ruff lint, mypy
```

The tests run headless - `tests/conftest.py` sets Qt's offscreen platform - so they need no
display, and none of them touch the network or a real Google Spreadsheet.

### Layout

```
strat_app/
  __main__.py         # QApplication and the window
  settings_holder.py  # reads sf_stratification_settings.toml
  sessions/           # all the logic, importing neither Qt nor any GUI library
  qt/                 # the widgets, which are the only thing that imports PySide6
main.py               # the entry point PyInstaller builds from
```

The split is the point: `sessions/` talks to the GUI through the protocols in
`sessions/view.py`, so all of it can be tested without a window. `qt/` implements those
protocols and does nothing else.

To create executables using pyinstaller (as we describe below), you need `hook-mip.py` to deal with [this error](https://github.com/coin-or/python-mip/issues/198).

Executables
-----------

You can download executables from the latest [releases page](https://github.com/sortitionfoundation/stratification-app/releases).  These are built by GitHub Actions.

### Manual builds

If you want to make an executable yourself, use [PyInstaller](https://pyinstaller.readthedocs.io/en/stable/).  The following set of commands, run in the root of the repo, create a single file executable in the folder `dist`.

``` sh
git pull
uv run pyinstaller strat-select.spec
```

The resulting executable will work on any computer running the same operating system as yours, i.e. Windows, Mac OS or Linux.  So if you run the above command on Linux, you can give the file to someone else running Linux. If the person who wants the app is running Windows, you need to run the above command on Windows.
