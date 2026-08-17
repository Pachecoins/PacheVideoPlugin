# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


SPEC_DIR = Path(SPECPATH)
ICON = Path(os.environ.get("PACHEVIDEO_ICON", ""))
VERSION_FILE = SPEC_DIR.parent / "packaging" / "windows" / "version_info.txt"
LOGO = SPEC_DIR.parent / "plugin" / "icons" / "logo.png"

if not ICON.is_file():
    raise SystemExit("PACHEVIDEO_ICON debe apuntar a PacheVideo.ico")
if not VERSION_FILE.is_file():
    raise SystemExit(f"No se encontró la metadata de versión: {VERSION_FILE}")
if not LOGO.is_file():
    raise SystemExit(f"No se encontró el logo: {LOGO}")

ctk_datas, ctk_binaries, ctk_hidden = collect_all("customtkinter")

a = Analysis(
    [str(SPEC_DIR / "desktop.py")],
    pathex=[str(SPEC_DIR)],
    binaries=[*ctk_binaries],
    datas=[(str(LOGO), "."), (str(ICON), "."), *ctk_datas],
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
    icon=str(ICON),
    version=str(VERSION_FILE),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PacheVideo",
)
