Strat App
=========

[![Build Status](https://travis-ci.com/sortitionfoundation/stratification-app.svg?branch=master)](https://travis-ci.com/sortitionfoundation/stratification-app)

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
- poetry

### Running in development

After cloning this repo, open a terminal in the root of the repo and run:

```
pip install eel
pip install cvxpy
pip install gspread
pip install mip
pip install toml
pip install oauth2client
poetry shell
python script.py
```

At this point you should have a window pop up and be able to interact with it, either via uploading .csv files or else by reading directly from a google sheet. You will only need to do those *pip install* commands once -- after that, you can just fire up the poetry shell and run *python script.py*

### Key files

The python command *python script.py* requires only:
 - script.py
 - stratification.py
 - all of the files in the folder *web*
 
 To use poetry (as we suggest above) to control dependencies, you need *pyproject.toml*
 
 To create exectuables using pyinstaller (as we describe below), you need *hook-mip.py*
 
Executables
---------

You can download executables from the latest releases page.

If you want to make an executable yourself, use [PyInstaller](https://pyinstaller.readthedocs.io/en/stable/).  The following command, run in the root of the repo, creates a single file executable at `dist/script` - you can rename it to whatever you want. You can then give it to someone running on the same **platform** as you, and they can run it immediately

The command is:

```
git pull
poetry shell
python -m eel script.py web --additional-hooks-dir=. --onefile --noconsole
```

**Platform** means Windows, Mac OS X or Linux.  So if you run the above command on Linux, you can give the file to someone else running Linux.  If the person who wants the app is running Windows, you need to run the above command on Windows.




