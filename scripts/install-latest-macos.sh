#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-${PACHEVIDEO_GITHUB_REPO:-}}"
if [[ -z "$REPO" ]] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ORIGIN="$(git remote get-url origin 2>/dev/null || true)"
  REPO="$(printf '%s' "$ORIGIN" | sed -E 's#^(https://github.com/|git@github.com:)##; s#\.git$##')"
fi
if [[ -z "$REPO" || "$REPO" != */* ]]; then
  echo "Uso: $0 OWNER/REPOSITORY" >&2
  exit 1
fi

ARCH="$(uname -m)"
case "$ARCH" in
  arm64|x86_64) ;;
  *) echo "Arquitectura no soportada: $ARCH" >&2; exit 1 ;;
esac

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
PKG="$TMP_DIR/PacheVideo-Premiere.pkg"
URL="https://github.com/$REPO/releases/latest/download/PacheVideo-Premiere-macOS-$ARCH.pkg"

echo "Descargando $URL"
curl --fail --location --retry 3 "$URL" --output "$PKG"
sudo installer -pkg "$PKG" -target /
open -a "PacheVideo Helper" || true

echo "PacheVideo quedó instalado. Reiniciá Premiere y abrí Ventana > UXP Plugins > PacheVideo Tools."
