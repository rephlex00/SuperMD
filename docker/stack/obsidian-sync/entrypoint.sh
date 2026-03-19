#!/bin/sh
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "[obsidian] Starting as UID=${PUID} GID=${PGID}"

groupmod -o -g "$PGID" obsidian
usermod  -o -u "$PUID" obsidian

chown obsidian:obsidian /home/obsidian
chown -R obsidian:obsidian /home/obsidian/.config /home/obsidian/.local 2>/dev/null || true
chown obsidian:obsidian /vault

# ── Start D-Bus + gnome-keyring at the entrypoint level ─────────────────────
# This ensures both the main process (sync.sh) and any `docker exec` sessions
# share the same D-Bus session bus and keyring, so manual `ob login` is visible
# to the polling loop in sync.sh.
DBUS_ENV="/home/obsidian/.dbus-env"

eval "$(gosu obsidian dbus-launch --sh-syntax 2>/dev/null)" || true
export DBUS_SESSION_BUS_ADDRESS

# Persist bus address so exec sessions can source it.
echo "export DBUS_SESSION_BUS_ADDRESS='${DBUS_SESSION_BUS_ADDRESS}'" > "$DBUS_ENV"
chown obsidian:obsidian "$DBUS_ENV"

# Unlock gnome-keyring with an empty password so libsecret can store creds.
gosu obsidian sh -c 'echo "" | gnome-keyring-daemon --unlock --components=secrets 2>/dev/null' || true

exec gosu obsidian "$@"
