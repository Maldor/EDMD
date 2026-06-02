# -*- mode: python ; coding: utf-8 -*-


from operator import iconcat


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
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='EDMD',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='images/edmd.ico'
)
