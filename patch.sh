#!/usr/bin/env zsh

set -euo pipefail

PATCH_DIR=".venv/lib/python3.11/site-packages"

patch -p1 -d "$PATCH_DIR" < supernotelib-ratta-fallback.patch
patch -p1 -d "$PATCH_DIR" < sn2md-year-month-day.patch
patch -p1 -d "$PATCH_DIR" < sn2md-metadata-dotmeta.patch
patch -p1 -d "$PATCH_DIR" < sn2md-images-subdir.patch
patch -p1 -d "$PATCH_DIR" < sn2md-prompt-context.patch
