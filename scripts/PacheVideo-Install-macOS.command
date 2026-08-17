#!/usr/bin/env bash
# PacheVideo macOS installer. Run this file from Terminal or double-click it.
set -euo pipefail

REPOSITORY="Pachecoins/PacheVideoPlugin"
RELEASE_TAG="${PACHEVIDEO_RELEASE_TAG:-v0.5.1}"

case "$(uname -m)" in
  arm64) ARCH="arm64" ;;
  x86_64) ARCH="x86_64" ;;
  *)
    echo "Esta arquitectura de Mac no está soportada: $(uname -m)" >&2
    exit 1
    ;;
esac

case "$RELEASE_TAG" in
  v[0-9]*.[0-9]*) ;;
  *)
    echo "La versión indicada no es válida." >&2
    exit 1
    ;;
esac

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

PACKAGE="PacheVideo-macOS-${ARCH}.pkg"
BASE_URL="https://github.com/${REPOSITORY}/releases/download/${RELEASE_TAG}"
PACKAGE_PATH="${TMP_DIR}/${PACKAGE}"
CHECKSUM_PATH="${PACKAGE_PATH}.sha256"

echo "PacheVideo para macOS"
echo "Versión: ${RELEASE_TAG} · Mac: ${ARCH}"
echo "Descargando instalador verificado…"

curl --fail --location --retry 3 --retry-delay 2 \
  --output "$PACKAGE_PATH" "$BASE_URL/$PACKAGE"
curl --fail --location --retry 3 --retry-delay 2 \
  --output "$CHECKSUM_PATH" "$BASE_URL/$PACKAGE.sha256"

EXPECTED_SUM="$(awk 'NR == 1 { print $1 }' "$CHECKSUM_PATH")"
ACTUAL_SUM="$(shasum -a 256 "$PACKAGE_PATH" | awk '{ print $1 }')"
if [[ -z "$EXPECTED_SUM" || "$EXPECTED_SUM" != "$ACTUAL_SUM" ]]; then
  echo "La verificación de seguridad del instalador falló. No se instaló nada." >&2
  exit 1
fi

echo "Archivo verificado. macOS pedirá tu contraseña para instalar PacheVideo."
sudo /usr/sbin/installer -pkg "$PACKAGE_PATH" -target /

echo "PacheVideo quedó instalado en Aplicaciones."
open -a "PacheVideo" || true
