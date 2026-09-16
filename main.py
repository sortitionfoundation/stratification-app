# ABOUTME: The entry point PyInstaller builds from - a plain script suits it better than -m.
# ABOUTME: Everything it does lives in strat_app.__main__.

import sys

from strat_app.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
