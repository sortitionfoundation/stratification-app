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

PyInstaller - once I've confirmed it actually works.
