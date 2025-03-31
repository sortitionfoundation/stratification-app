from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs


# this function came from this comment:
# https://github.com/coin-or/python-mip/issues/198#issuecomment-1640309437
def hook(hook_api):
    packages = ['mip']
    for package in packages:
        datas, binaries, hiddenimports = collect_all(package)
        binary_paths = set(b[0] for b in binaries)
        # find any xyz.so libraries that don't start with "lib"
        binaries += [b for b in collect_dynamic_libs(package, search_patterns=["*.so"]) if b[0] not in binary_paths]
        hook_api.add_datas(datas)
        hook_api.add_binaries(binaries)
        hook_api.add_imports(*hiddenimports)
