#!/usr/bin/env bash
# Wrap the .app into a drag-to-Applications DMG.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST="$ROOT/dist/macos"
APP="$DIST/SuperMD.app"
VERSION="${SUPERMD_VERSION:-0.1.0}"
DMG="$DIST/SuperMD-$VERSION.dmg"

if [[ ! -d "$APP" ]]; then
    echo "$APP not found. Run build-app.sh first." >&2
    exit 1
fi

if ! command -v create-dmg >/dev/null 2>&1; then
    echo "create-dmg not found. Install with: brew install create-dmg" >&2
    exit 1
fi

rm -f "$DMG"

create-dmg \
    --volname "SuperMD $VERSION" \
    --window-size 540 360 \
    --icon-size 96 \
    --icon "SuperMD.app" 130 180 \
    --app-drop-link 410 180 \
    --hide-extension "SuperMD.app" \
    --no-internet-enable \
    "$DMG" \
    "$APP"

echo "Built: $DMG"
