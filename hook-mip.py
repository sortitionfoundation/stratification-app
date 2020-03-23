# Ensures that PyInstaller copies the CBC binaries for the mip library.
# See https://github.com/coin-or/python-mip/issues/76.
# Should become obsolete once https://github.com/pyinstaller/pyinstaller/pull/4762
# gets merged and makes it into the pyinstaller release.

import os
from PyInstaller.utils.hooks import get_package_paths

datas = []
_, mip_path = get_package_paths("mip")
lib_path = os.path.join(mip_path, "libraries")

for f in os.listdir(lib_path):
    if f.endswith(".so") or f.endswith(".dll") or f.endswith(".dylib"):
        datas.append((os.path.join(lib_path, f), "mip/libraries"))
