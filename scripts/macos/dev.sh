#!/usr/bin/env bash
# Dev runner: launches the SwiftUI app in debug mode against a development
# sidecar (python -m supermd_sidecar from the repo root).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# Tell the app where the repo lives — its argv[0]-based fallback walk doesn't
# always survive `swift run`'s argv shape.
export SUPERMD_REPO_ROOT="$ROOT"
cd "$ROOT/app"

# Ensure deps are installed in the user's Python env so the sidecar runs
if ! python3 -c "import supermd_sidecar" 2>/dev/null; then
    echo "Installing sidecar (editable)…"
    uv pip install -e ".." || pip install -e ..
    uv pip install -e "../sidecar" || pip install -e ../sidecar
fi

# swift run prints both app stdout and the sidecar's stderr (which the app
# forwards). Ctrl-C stops both.
swift run SuperMD
