# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['edmd.py'],
    pathex=[],
    binaries=[],
    datas=[('core', 'core'),
           ('components', 'components'),
           ('data', 'data'),
           ('docs', 'docs'),
           ('electron', 'electron'),
           ('fonts', 'fonts'),
           ('images', 'images'),
           ('themes', 'themes'),
           ('tui', 'tui')
    ],
    hiddenimports=['sqlite3'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='edmd_debug',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='edmd',
)
