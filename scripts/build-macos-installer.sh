#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="0.2.0"
FFMPEG_VERSION="8.0.1"
FFMPEG_SHA256="05ee0b03119b45c0bdb4df654b96802e909e0a752f72e4fe3794f487229e5a41"
ARCH="$(uname -m)"

case "$ARCH" in
  arm64|x86_64) ;;
  *) echo "Arquitectura macOS no soportada: $ARCH" >&2; exit 1 ;;
esac

BUILD="$ROOT/.build-macos-$ARCH"
VENV="$BUILD/venv"
FFMPEG_PREFIX="$BUILD/ffmpeg-prefix"
PYI_DIST="$BUILD/pyinstaller-dist"
PKG_ROOT="$BUILD/pkgroot"
CCX="$BUILD/PacheVideo-Premiere.ccx"
DIST="$ROOT/dist"
FINAL_PKG="$DIST/PacheVideo-Premiere-macOS-$ARCH.pkg"

[[ -f "$ROOT/plugin/manifest.json" ]] || { echo "Falta plugin/manifest.json" >&2; exit 1; }
[[ -f "$ROOT/companion/server.py" ]] || { echo "Falta companion/server.py" >&2; exit 1; }

command -v brew >/dev/null 2>&1 || { echo "Instalá Homebrew desde https://brew.sh" >&2; exit 1; }
brew install python@3.14 pkg-config x264 lame
PYTHON_BIN="$(brew --prefix python@3.14)/bin/python3.14"

rm -rf "$BUILD"
mkdir -p "$BUILD" "$DIST"

ARCHIVE="$BUILD/ffmpeg-$FFMPEG_VERSION.tar.xz"
curl --fail --location --retry 3 \
  "https://ffmpeg.org/releases/ffmpeg-$FFMPEG_VERSION.tar.xz" \
  --output "$ARCHIVE"
echo "$FFMPEG_SHA256  $ARCHIVE" | shasum -a 256 --check
tar -xf "$ARCHIVE" -C "$BUILD"

pushd "$BUILD/ffmpeg-$FFMPEG_VERSION" >/dev/null
PKG_CONFIG_PATH="$(brew --prefix x264)/lib/pkgconfig:$(brew --prefix lame)/lib/pkgconfig" \
  ./configure \
    --prefix="$FFMPEG_PREFIX" \
    --cc=clang \
    --enable-gpl \
    --enable-libx264 \
    --enable-libmp3lame \
    --enable-audiotoolbox \
    --enable-videotoolbox \
    --disable-debug \
    --disable-doc \
    --disable-ffplay \
    --disable-ffprobe
make -j"$(sysctl -n hw.logicalcpu)"
make install
popd >/dev/null

FFMPEG_BIN="$FFMPEG_PREFIX/bin/ffmpeg"
"$FFMPEG_BIN" -version | head -n 1 | grep -F "ffmpeg version $FFMPEG_VERSION"

ICONSET="$BUILD/PacheVideo.iconset"
ICON="$BUILD/PacheVideo.icns"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$ROOT/plugin/icons/logo.png" \
    --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" "$ROOT/plugin/icons/logo.png" \
    --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$ICON"

"$PYTHON_BIN" -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -r "$ROOT/companion/requirements.txt"

PACHEVIDEO_FFMPEG="$FFMPEG_BIN" \
PACHEVIDEO_ICON="$ICON" \
MACOS_APPLICATION_IDENTITY="${MACOS_APPLICATION_IDENTITY:-}" \
  "$VENV/bin/pyinstaller" \
    --noconfirm \
    --clean \
    --distpath "$PYI_DIST" \
    --workpath "$BUILD/pyinstaller-work" \
    "$ROOT/companion/PacheVideoHelper.spec"

HELPER_APP="$PYI_DIST/PacheVideo Helper.app"
[[ -d "$HELPER_APP" ]] || { echo "PyInstaller no generó $HELPER_APP" >&2; exit 1; }

if [[ -n "${MACOS_APPLICATION_IDENTITY:-}" ]]; then
  codesign --force --deep --options runtime --timestamp \
    --sign "$MACOS_APPLICATION_IDENTITY" "$HELPER_APP"
else
  codesign --force --deep --sign - "$HELPER_APP"
fi
codesign --verify --deep --strict --verbose=2 "$HELPER_APP"

pushd "$ROOT/plugin" >/dev/null
zip -q -r "$CCX" . -x '*.DS_Store' '__MACOSX/*'
popd >/dev/null
unzip -p "$CCX" manifest.json >/dev/null

mkdir -p \
  "$PKG_ROOT/Applications" \
  "$PKG_ROOT/Library/Application Support/PacheVideo" \
  "$PKG_ROOT/Library/LaunchAgents"
cp -R "$HELPER_APP" "$PKG_ROOT/Applications/"
cp "$CCX" "$PKG_ROOT/Library/Application Support/PacheVideo/PacheVideo-Premiere.ccx"
cp "$ROOT/packaging/macos/com.pachevideo.helper.plist" \
  "$PKG_ROOT/Library/LaunchAgents/com.pachevideo.helper.plist"

chmod +x "$ROOT/packaging/macos/pkg-scripts/preinstall" \
  "$ROOT/packaging/macos/pkg-scripts/postinstall"

PKGBUILD_ARGS=(
  --root "$PKG_ROOT"
  --scripts "$ROOT/packaging/macos/pkg-scripts"
  --identifier "com.pachevideo.premiere.installer"
  --version "$VERSION"
  --install-location /
)
if [[ -n "${MACOS_INSTALLER_IDENTITY:-}" ]]; then
  PKGBUILD_ARGS+=(--sign "$MACOS_INSTALLER_IDENTITY")
fi
pkgbuild "${PKGBUILD_ARGS[@]}" "$FINAL_PKG"

pkgutil --check-signature "$FINAL_PKG" || true

if [[ -n "${APPLE_ID:-}" && -n "${APPLE_TEAM_ID:-}" && -n "${APPLE_APP_PASSWORD:-}" ]]; then
  xcrun notarytool submit "$FINAL_PKG" \
    --apple-id "$APPLE_ID" \
    --team-id "$APPLE_TEAM_ID" \
    --password "$APPLE_APP_PASSWORD" \
    --wait
  xcrun stapler staple "$FINAL_PKG"
  xcrun stapler validate "$FINAL_PKG"
fi

shasum -a 256 "$FINAL_PKG" >"$FINAL_PKG.sha256"
echo "Instalador generado: $FINAL_PKG"
