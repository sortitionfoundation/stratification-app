Strat App
=========

A simple GUI for stratification for sortition/citizen's assemblies.

About
-----

blah

Development
-----------

The app is built using [eel](https://github.com/ChrisKnott/Eel) - a framework that allows the GUI to be defined in HTML and CSS, but then some basic JavaScript can call Python and I can do the heavy lifting in Python.

### Install for development

First you need to have the following installed:

- git
- python 3.6
- [pipenv](https://docs.pipenv.org/en/latest/)
- a recent version of Chrome or Chromium

### Running in development

After cloning this repo, open a terminal in the root of the repo and run:

```
pipenv install
pipenv shell
python script.py
```

At which point you should have a window pop up and be able to interact with it.

Releasing
---------

To make a single file executable, we use [PyInstaller](https://pyinstaller.readthedocs.io/en/stable/).  The following command, run in the root of the repo, creates a single file executable at `dist/script` - you can rename it to whatever you want. You can then give it to someone running on the same **platform** as you, and they can run it immediately

The command is:

```
python -m eel script.py web --onefile --noconsole
```

**Platform** means Windows, Mac OS X or Linux.  So if you run the above command on Linux, you can give the file to someone else running Linux.  So if the person who wants the app is running Windows, you need to run the above command on Windows.

Note that on Windows you need to install an extra package:

```
pip install pypiwin32
```

This should be done by `pipenv install` but I may have got the syntax wrong.
