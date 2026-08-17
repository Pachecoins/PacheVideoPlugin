# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


SPEC_DIR = Path(SPECPATH)
FFMPEG = Path(os.environ.get("PACHEVIDEO_FFMPEG", ""))
ICON = Path(os.environ.get("PACHEVIDEO_ICON", ""))
VERSION_FILE = SPEC_DIR.parent / "packaging" / "windows" / "helper_version_info.txt"

if not FFMPEG.is_file():
    raise SystemExit("PACHEVIDEO_FFMPEG debe apuntar a ffmpeg.exe")
if not ICON.is_file():
    raise SystemExit("PACHEVIDEO_ICON debe apuntar a PacheVideo.ico")
if not VERSION_FILE.is_file():
    raise SystemExit(f"No se encontró la metadata de versión: {VERSION_FILE}")

yt_datas, yt_binaries, yt_hidden = collect_all("yt_dlp")

a = Analysis(
    [str(SPEC_DIR / "server.py")],
    pathex=[str(SPEC_DIR)],
    binaries=[(str(FFMPEG), "."), *yt_binaries],
    datas=[*yt_datas],
    hiddenimports=[*yt_hidden],
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
    name="PacheVideoHelper",
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
    name="PacheVideoHelper",
)
