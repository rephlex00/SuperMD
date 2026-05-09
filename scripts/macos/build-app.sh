#!/usr/bin/env bash
# Build the SwiftUI app and assemble a .app bundle with the bundled sidecar.
#
# Output: dist/macos/SuperMD.app
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP_SRC="$ROOT/app"
DIST="$ROOT/dist/macos"
APP_BUNDLE="$DIST/SuperMD.app"

if [[ ! -x "$DIST/supermd-sidecar" ]]; then
    echo "Sidecar binary missing. Run scripts/macos/build-sidecar.sh first." >&2
    exit 1
fi

# 1. Build the Swift executable
cd "$APP_SRC"
swift build -c release --arch arm64

BIN="$APP_SRC/.build/arm64-apple-macosx/release/SuperMD"
if [[ ! -x "$BIN" ]]; then
    echo "swift build did not produce $BIN" >&2
    exit 1
fi

# 2. Build the .app bundle structure
rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

cp "$BIN" "$APP_BUNDLE/Contents/MacOS/SuperMD"
cp "$DIST/supermd-sidecar" "$APP_BUNDLE/Contents/Resources/supermd-sidecar"
cp "$APP_SRC/Resources/Info.plist" "$APP_BUNDLE/Contents/Info.plist"

chmod +x "$APP_BUNDLE/Contents/MacOS/SuperMD"
chmod +x "$APP_BUNDLE/Contents/Resources/supermd-sidecar"

# 3. (Optional) Codesign if APPLE_TEAM_ID is set
if [[ -n "${APPLE_TEAM_ID:-}" ]]; then
    echo "Codesigning with team $APPLE_TEAM_ID"
    codesign --force --deep --options runtime \
        --sign "Developer ID Application: $APPLE_TEAM_ID" \
        "$APP_BUNDLE/Contents/Resources/supermd-sidecar"
    codesign --force --deep --options runtime \
        --sign "Developer ID Application: $APPLE_TEAM_ID" \
        "$APP_BUNDLE"
    codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"
else
    echo "APPLE_TEAM_ID not set; skipping codesign (app will only run locally)"
fi

echo "Built: $APP_BUNDLE"
