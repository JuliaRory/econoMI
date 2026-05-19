# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ["start.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("resources", "resources"),
        ("styles", "styles"),
        ("drivers", "drivers"),
        ("settings/response_keys.json", "settings"),
    ],
    hiddenimports=[
        "PyQt5.QtMultimedia",
        "PyQt5.QtMultimediaWidgets",
    ],
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
    name="econoMI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="resources/icon_hand.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="econoMI",
)
