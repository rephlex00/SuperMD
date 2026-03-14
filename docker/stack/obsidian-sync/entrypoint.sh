#!/bin/sh
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "[obsidian] Starting as UID=${PUID} GID=${PGID}"

groupmod -o -g "$PGID" obsidian
usermod  -o -u "$PUID" obsidian

chown obsidian:obsidian /home/obsidian
chown obsidian:obsidian /vault

exec gosu obsidian "$@"
