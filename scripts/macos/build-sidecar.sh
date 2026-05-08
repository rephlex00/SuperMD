#!/usr/bin/env bash
# Build a single-binary Python sidecar for inclusion in the .app bundle.
#
# Output: dist/macos/supermd-sidecar
#
# Uses PyInstaller. The built binary contains the supermd engine, the sidecar
# package, all `llm` plugins, and the sncloud fork. The user's Mac never runs
# `pip` or sees Python on its PATH.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST="$ROOT/dist/macos"
WORK="$ROOT/dist/macos/.build"

mkdir -p "$DIST" "$WORK"

cd "$WORK"

# Use uv to materialise a clean venv with everything we need.
if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found. Install via: brew install uv" >&2
    exit 1
fi

uv venv .venv-build
# shellcheck disable=SC1091
source .venv-build/bin/activate

uv pip install \
    -e "$ROOT" \
    -e "$ROOT/sidecar" \
    pyinstaller \
    llm-ollama \
    llm-gemini \
    llm-claude-3

pyinstaller \
    --onefile \
    --name supermd-sidecar \
    --noconfirm \
    --clean \
    --collect-all supermd \
    --collect-all supermd_sidecar \
    --collect-all sncloud \
    --collect-submodules llm \
    --collect-submodules llm_ollama \
    --collect-submodules llm_gemini \
    --collect-submodules llm_claude_3 \
    --hidden-import keyring.backends.macOS \
    --distpath "$DIST" \
    --workpath "$WORK/build" \
    --specpath "$WORK" \
    "$ROOT/sidecar/src/supermd_sidecar/__main__.py"

echo "Built: $DIST/supermd-sidecar"
ls -lah "$DIST/supermd-sidecar"
