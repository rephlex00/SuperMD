#!/usr/bin/env bash
# Wrap the .app into a drag-to-Applications DMG using hdiutil directly.
# We avoid create-dmg here because its AppleScript-driven styling step
# times out in headless / CI / automation-restricted environments —
# producing leftover rw.*.dmg files and no final image.
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

# Clean up any prior runs (including create-dmg leftovers).
rm -f "$DMG" "$DIST"/rw.*.dmg

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# Stage the app + an Applications symlink so the user gets drag-to-install.
cp -R "$APP" "$STAGE/SuperMD.app"
ln -s /Applications "$STAGE/Applications"

hdiutil create \
    -volname "SuperMD $VERSION" \
    -srcfolder "$STAGE" \
    -fs HFS+ \
    -format UDZO \
    -imagekey zlib-level=9 \
    -ov \
    "$DMG"

echo "Built: $DMG"
ls -lh "$DMG"
