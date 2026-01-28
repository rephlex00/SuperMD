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
# We only chown the output and config directories. Input might be read-only.
# Ensure directories are owned by the user
# We only chown the output and config directories. Input might be read-only.

# Ensure directories are owned by the user
# We only chown the output and config directories. Input might be read-only.
chown -R "$PUID":"$PGID" /data/out /config

# Directory validation
if [ ! -d "/data/in" ] || [ -z "$(ls -A /data/in 2>/dev/null)" ]; then
    echo "WARNING: /data/in appears to be empty or missing. Please ensure your input volume is mounted correctly."
fi

if [ ! -w "/data/out" ]; then
    echo "WARNING: /data/out is not writable. Please check permissions."
fi

# Handle known command invocations
# First, strip 'sn2md-cli' if present to normalize
if [ "$1" = "sn2md-cli" ]; then
    shift
fi

# Determine Configuration
# If /config/jobs.yaml exists, valid, use it.
# Otherwise fall back to internal default.
CONFIG_FILE="/app/config/docker-jobs.yaml"
if [ -f "/config/jobs.yaml" ]; then
    echo "Found custom configuration at /config/jobs.yaml"
    CONFIG_FILE="/config/jobs.yaml"
fi
CONFIG_ARG="--config $CONFIG_FILE"

# Handling 'watch' command injection
if [ "$1" = "watch" ]; then
    shift
    # Inject our determined config.
    # User arguments ("$@") come LAST, so they can override if the user explicitly provided --config in CMD or run args.
    exec gosu sn2md sn2md-cli watch $CONFIG_ARG "$@"
fi

# Pass through other commands
if [ "$1" = "run" ] || [ "$1" = "file" ] || [ "$1" = "directory" ] || [ "$1" = "rebuild-meta" ] || [ "$1" = "clean-meta" ] || [ "$1" = "meta" ] || [ "${1:0:1}" = "-" ]; then
    exec gosu sn2md sn2md-cli "$@"
fi

# Otherwise execute arbitrary command as root
exec "$@"
