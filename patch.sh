#!/usr/bin/env zsh

set -euo pipefail

PATCH_DIR="$(".venv/bin/python" -c "import site; print(site.getsitepackages()[0])")"

patch -p1 -d "$PATCH_DIR" < supernotelib-ratta-fallback.patch
patch -p1 -d "$PATCH_DIR" < sn2md-year-month-day.patch
patch -p1 -d "$PATCH_DIR" < sn2md-metadata-dotmeta.patch
patch -p1 -d "$PATCH_DIR" < sn2md-images-subdir.patch
patch -p1 -d "$PATCH_DIR" < sn2md-prompt-context.patch
