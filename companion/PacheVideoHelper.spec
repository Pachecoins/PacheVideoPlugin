# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


SPEC_DIR = Path(SPECPATH)
ROOT = SPEC_DIR.parent
FFMPEG = Path(os.environ.get("PACHEVIDEO_FFMPEG", ""))
ICON = Path(os.environ.get("PACHEVIDEO_ICON", ""))
CODESIGN_IDENTITY = os.environ.get("MACOS_APPLICATION_IDENTITY") or None

if not FFMPEG.is_file():
    raise SystemExit("PACHEVIDEO_FFMPEG debe apuntar al binario ffmpeg para macOS")
if not ICON.is_file():
    raise SystemExit("PACHEVIDEO_ICON debe apuntar a PacheVideo.icns")

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
    name="PacheVideoHelper",
)

app = BUNDLE(
    coll,
    name="PacheVideo Helper.app",
    icon=str(ICON),
    bundle_identifier="com.pachevideo.helper",
    version="0.2.3",
    codesign_identity=CODESIGN_IDENTITY,
    info_plist={
        "CFBundleDisplayName": "PacheVideo Helper",
        "CFBundleName": "PacheVideo Helper",
        "LSMinimumSystemVersion": "13.0",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
    },
)
