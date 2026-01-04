#!/bin/bash
set -e

# Default to 1000 if not set
PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Create group with PGID if it doesn't exist
if ! getent group sn2md > /dev/null 2>&1; then
    groupadd -g "$PGID" sn2md
fi

# Create user with PUID if it doesn't exist
if ! id -u sn2md > /dev/null 2>&1; then
    useradd -u "$PUID" -g "$PGID" -m -d /home/sn2md -s /bin/bash sn2md
fi

# Ensure directories are owned by the user
# We only chown the data/config directories to avoid messing with system files
chown -R "$PUID":"$PGID" /data /config

# If command starts with known subcommands or flags, prepend sn2md-cli and run as user
if [ "$1" = "watch" ] || [ "$1" = "run" ] || [ "$1" = "file" ] || [ "$1" = "directory" ] || [ "${1:0:1}" = "-" ]; then
    exec gosu sn2md sn2md-cli "$@"
fi

# If command is explicitly sn2md-cli, run as user matches
if [ "$1" = "sn2md-cli" ]; then
    shift
    exec gosu sn2md sn2md-cli "$@"
fi

# Otherwise execute arbitrary command as root (helpful for debugging/maintenance)
exec "$@"
