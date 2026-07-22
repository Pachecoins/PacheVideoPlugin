# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


SPEC_DIR = Path(SPECPATH)
ICON = Path(os.environ.get("PACHEVIDEO_ICON", ""))
LOGO = SPEC_DIR.parent / "plugin" / "icons" / "logo.png"
CODESIGN_IDENTITY = os.environ.get("MACOS_APPLICATION_IDENTITY") or None

if not ICON.is_file():
    raise SystemExit("PACHEVIDEO_ICON debe apuntar a PacheVideo.icns")
if not LOGO.is_file():
    raise SystemExit(f"No se encontró el logo: {LOGO}")

ctk_datas, ctk_binaries, ctk_hidden = collect_all("customtkinter")

a = Analysis(
    [str(SPEC_DIR / "desktop.py")],
    pathex=[str(SPEC_DIR)],
    binaries=[*ctk_binaries],
    datas=[(str(LOGO), "."), *ctk_datas],
    hiddenimports=[*ctk_hidden],
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
    name="PacheVideo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=CODESIGN_IDENTITY,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PacheVideo",
)

app = BUNDLE(
    coll,
    name="PacheVideo.app",
    icon=str(ICON),
    bundle_identifier="com.pachevideo.app",
    version="0.3.0",
    codesign_identity=CODESIGN_IDENTITY,
    info_plist={
        "CFBundleDisplayName": "PacheVideo",
        "CFBundleName": "PacheVideo",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
    },
)
