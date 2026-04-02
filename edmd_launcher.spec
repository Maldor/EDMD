# edmd_launcher.spec — PyInstaller spec for EDMD.exe (Windows launcher stub)
#
# Build with:
#   pyinstaller edmd_launcher.spec
#
# The resulting dist\EDMD\EDMD.exe is a small launcher that locates the MSYS2
# Python interpreter and the EDMD source (installed alongside) and execs edmd.py.
# It does NOT bundle GTK4, PyGObject, or the EDMD source — those are installed
# separately by the Inno Setup installer.
#
# This design preserves the git-based upgrade path (edmd.py --upgrade).

import glob
import os

block_cipher = None

# ── Bundle libgcc_s_seh-1.dll ─────────────────────────────────────────────────
# PyInstaller compiled with the MSYS2 MinGW64 toolchain depends on this GCC
# runtime DLL. Without it, EDMD.exe fails immediately with "libgcc_s_seh-1.dll
# was not found". We bundle it alongside the exe so users don't need MinGW on
# PATH. Search common MSYS2 install locations; fall back gracefully if absent
# (e.g., when building with UCRT64 toolchain which uses a different runtime).
_GCC_DLL_NAME = "libgcc_s_seh-1.dll"
_GCC_SEARCH   = [
    r"C:\msys64\mingw64\bin",
    r"C:\msys64\ucrt64\bin",
    r"C:\msys2\mingw64\bin",
    r"C:\msys2\ucrt64\bin",
    os.path.join(os.environ.get("MSYS2_ROOT", r"C:\msys64"), "mingw64", "bin"),
    os.path.join(os.environ.get("MSYS2_ROOT", r"C:\msys64"), "ucrt64",  "bin"),
]
_gcc_dll = None
for _d in _GCC_SEARCH:
    _candidate = os.path.join(_d, _GCC_DLL_NAME)
    if os.path.isfile(_candidate):
        _gcc_dll = _candidate
        break
# Also try glob for non-standard MSYS2 install paths
if _gcc_dll is None:
    _hits = (
        glob.glob(r"C:\msys*\mingw64\bin\libgcc_s_seh-1.dll") +
        glob.glob(r"C:\msys*\ucrt64\bin\libgcc_s_seh-1.dll")
    )
    if _hits:
        _gcc_dll = _hits[0]

_extra_binaries = [(_gcc_dll, ".")] if _gcc_dll else []
# ─────────────────────────────────────────────────────────────────────────────

a = Analysis(
    [os.path.join(SPECPATH, 'edmd_launcher.py')],
    pathex=[SPECPATH],
    binaries=_extra_binaries,
    datas=[],
    hiddenimports=[
        'ctypes',
        'subprocess',
        'pathlib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude everything not needed by the tiny launcher
        'gi', 'gtk', 'glib', 'gobject',
        'discord_webhook', 'cryptography', 'psutil',
        'tkinter', 'matplotlib', 'numpy', 'PIL',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EDMD',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,             # keep console window — EDMD is a terminal daemon
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                # set to 'installer\\edmd.ico' if icon exists
    version=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EDMD',
)
