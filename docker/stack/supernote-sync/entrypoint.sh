#!/bin/sh
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "[sncloud] Starting as UID=${PUID} GID=${PGID}"

groupmod -o -g "$PGID" sncloud
usermod  -o -u "$PUID" sncloud

chown sncloud:sncloud /home/sncloud
chown sncloud:sncloud /notes

exec gosu sncloud "$@"
