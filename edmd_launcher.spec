# edmd_launcher.spec -- PyInstaller spec for EDMD.exe (Windows launcher stub)
#
# Build with:
#   pyinstaller edmd_launcher.spec --noconfirm --clean
#
# The resulting dist\EDMD\EDMD.exe is a small launcher stub that locates the
# bundled runtime (dist\runtime\python.exe, shipped by the Inno Setup installer)
# or a local MSYS2 installation as a fallback, and execs edmd.py.
#
# This design preserves the git-based upgrade path: edmd.py and the EDMD source
# live in a real git clone (src\) that is updated via "EDMD.exe --upgrade".

import os

block_cipher = None

a = Analysis(
    [os.path.join(SPECPATH, 'edmd_launcher.py')],
    pathex=[SPECPATH],
    binaries=[],
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
        # Exclude everything not needed by the tiny launcher stub
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
    console=True,             # keep console window -- EDMD is a terminal daemon
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                # set to 'installer\\edmd.ico' if present
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
