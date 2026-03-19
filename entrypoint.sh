#!/bin/sh
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "[supermd] Starting as UID=${PUID} GID=${PGID}"

groupmod -o -g "$PGID" supermd
usermod  -o -u "$PUID" supermd

# Re-own the home directory after the UID/GID change so the llm library can
# write its config and logs to ~/.config/llm/. Volume-mounted paths (/input,
# /output, /config) are intentionally left alone — ownership there is
# controlled by the host, and PUID/PGID should already match your host user.
chown supermd:supermd /home/supermd

exec gosu supermd "$@"
