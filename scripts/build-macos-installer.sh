#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="0.3.0"
FFMPEG_VERSION="8.0.1"
FFMPEG_SHA256="05ee0b03119b45c0bdb4df654b96802e909e0a752f72e4fe3794f487229e5a41"
LAME_VERSION="3.101"
LAME_SHA256="7578af6eebd578b2bd64e468fac4ae1f03670a7e028166e67f855674b9b6aeac"
ARCH="$(uname -m)"

case "$ARCH" in
  arm64|x86_64) ;;
  *) echo "Arquitectura macOS no soportada: $ARCH" >&2; exit 1 ;;
esac

BUILD="$ROOT/.build-macos-$ARCH"
VENV="$BUILD/venv"
FFMPEG_PREFIX="$BUILD/ffmpeg-prefix"
LAME_PREFIX="$BUILD/lame-prefix"
PYI_DIST="$BUILD/pyinstaller-dist"
PKG_ROOT="$BUILD/pkgroot"
CCX="$BUILD/PacheVideo-Premiere.ccx"
DIST="$ROOT/dist"
FINAL_PKG="$DIST/PacheVideo-Premiere-macOS-$ARCH.pkg"

[[ -f "$ROOT/plugin/manifest.json" ]] || { echo "Falta plugin/manifest.json" >&2; exit 1; }
[[ -f "$ROOT/companion/server.py" ]] || { echo "Falta companion/server.py" >&2; exit 1; }

command -v brew >/dev/null 2>&1 || { echo "Instalá Homebrew desde https://brew.sh" >&2; exit 1; }
brew install python@3.14 python-tk@3.14 pkg-config x264 nasm
PYTHON_BIN="$(brew --prefix python@3.14)/bin/python3.14"

rm -rf "$BUILD"
mkdir -p "$BUILD" "$DIST"

LAME_ARCHIVE="$BUILD/lame-$LAME_VERSION.tar.gz"
curl --fail --location --retry 3 \
  "https://downloads.sourceforge.net/project/lame/lame/$LAME_VERSION/lame-$LAME_VERSION.tar.gz" \
  --output "$LAME_ARCHIVE"
echo "$LAME_SHA256  $LAME_ARCHIVE" | shasum -a 256 --check
tar -xf "$LAME_ARCHIVE" -C "$BUILD"

pushd "$BUILD/lame-$LAME_VERSION" >/dev/null
./configure \
  --prefix="$LAME_PREFIX" \
  --disable-shared \
  --enable-static \
  --disable-decoder \
  --disable-frontend
make -j"$(sysctl -n hw.logicalcpu)"
make install
popd >/dev/null

ARCHIVE="$BUILD/ffmpeg-$FFMPEG_VERSION.tar.xz"
curl --fail --location --retry 3 \
  "https://ffmpeg.org/releases/ffmpeg-$FFMPEG_VERSION.tar.xz" \
  --output "$ARCHIVE"
echo "$FFMPEG_SHA256  $ARCHIVE" | shasum -a 256 --check
tar -xf "$ARCHIVE" -C "$BUILD"

pushd "$BUILD/ffmpeg-$FFMPEG_VERSION" >/dev/null
PKG_CONFIG_PATH="$(brew --prefix x264)/lib/pkgconfig" \
  ./configure \
    --prefix="$FFMPEG_PREFIX" \
    --cc=clang \
    --extra-cflags="-I$LAME_PREFIX/include" \
    --extra-ldflags="-L$LAME_PREFIX/lib" \
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
"$FFMPEG_BIN" -hide_banner -encoders | grep -F "libmp3lame"
"$FFMPEG_BIN" -hide_banner -encoders | grep -F "libx264"

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

PACHEVIDEO_ICON="$ICON" \
MACOS_APPLICATION_IDENTITY="${MACOS_APPLICATION_IDENTITY:-}" \
  "$VENV/bin/pyinstaller" \
    --noconfirm \
    --clean \
    --distpath "$PYI_DIST" \
    --workpath "$BUILD/pyinstaller-work" \
    "$ROOT/companion/PacheVideo.spec"

HELPER_APP="$PYI_DIST/PacheVideo Helper.app"
PACHEVIDEO_APP="$PYI_DIST/PacheVideo.app"
[[ -d "$HELPER_APP" ]] || { echo "PyInstaller no generó $HELPER_APP" >&2; exit 1; }
[[ -d "$PACHEVIDEO_APP" ]] || { echo "PyInstaller no generó $PACHEVIDEO_APP" >&2; exit 1; }
BUNDLED_FFMPEG="$(find "$HELPER_APP" -type f -name ffmpeg -print -quit)"
[[ -n "$BUNDLED_FFMPEG" && -x "$BUNDLED_FFMPEG" ]] || {
  echo "El Helper no contiene un FFmpeg ejecutable" >&2
  exit 1
}
"$BUNDLED_FFMPEG" -version | head -n 1 | grep -F "ffmpeg version $FFMPEG_VERSION"
if otool -L "$BUNDLED_FFMPEG" | grep -E '/(opt/homebrew|usr/local)/(Cellar|opt)/'; then
  echo "FFmpeg conserva dependencias de Homebrew fuera del bundle" >&2
  exit 1
fi

for app in "$HELPER_APP" "$PACHEVIDEO_APP"; do
  if [[ -n "${MACOS_APPLICATION_IDENTITY:-}" ]]; then
    codesign --force --deep --options runtime --timestamp \
      --sign "$MACOS_APPLICATION_IDENTITY" "$app"
  else
    codesign --force --deep --sign - "$app"
  fi
  codesign --verify --deep --strict --verbose=2 "$app"
done

pushd "$ROOT/plugin" >/dev/null
zip -q -r "$CCX" . -x '*.DS_Store' '__MACOSX/*'
popd >/dev/null
unzip -p "$CCX" manifest.json >/dev/null

mkdir -p \
  "$PKG_ROOT/Applications" \
  "$PKG_ROOT/Library/Application Support/PacheVideo" \
  "$PKG_ROOT/Library/LaunchAgents"
cp -R "$HELPER_APP" "$PKG_ROOT/Applications/"
cp -R "$PACHEVIDEO_APP" "$PKG_ROOT/Applications/"
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
