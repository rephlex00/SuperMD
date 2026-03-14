#!/bin/sh
set -e

echo "[obsidian] obsidian-headless $(ob --version 2>/dev/null || echo 'version unknown')"

# ── Helper: read a secret file ──────────────────────────────────────────────
read_secret() {
    file="/run/secrets/$1"
    if [ -f "$file" ]; then
        cat "$file" | tr -d '\n'
    else
        echo ""
    fi
}

# ── Authentication ──────────────────────────────────────────────────────────
# Path 1 (preferred): Use OBSIDIAN_AUTH_TOKEN if the secret file exists.
# Path 2 (fallback):  Start D-Bus + gnome-keyring, then ob login with creds.
# Path 3 (escape):    Run `docker compose exec obsidian-sync ob login` manually.

AUTH_TOKEN=$(read_secret "obsidian_auth_token")
OB_EMAIL=$(read_secret "obsidian_email")
OB_PASSWORD=$(read_secret "obsidian_password")

if [ -n "$AUTH_TOKEN" ]; then
    echo "[obsidian] Using auth token from secret (keyring bypass)"
    export OBSIDIAN_AUTH_TOKEN="$AUTH_TOKEN"
elif [ -n "$OB_EMAIL" ] && [ -n "$OB_PASSWORD" ]; then
    echo "[obsidian] Logging in with email/password..."

    # Start D-Bus session if not already running.
    if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
        eval "$(dbus-launch --sh-syntax 2>/dev/null)" || true
        export DBUS_SESSION_BUS_ADDRESS
    fi

    # Unlock gnome-keyring with an empty password so libsecret can store creds.
    echo "" | gnome-keyring-daemon --unlock --components=secrets 2>/dev/null || true

    ob login --email "$OB_EMAIL" --password "$OB_PASSWORD" || {
        echo "[obsidian] WARNING: automated login failed."
        echo "[obsidian] You can log in manually with:"
        echo "[obsidian]   docker compose exec obsidian-sync ob login"
        echo "[obsidian] Waiting 60s before retrying..."
        sleep 60
        exit 1
    }
    echo "[obsidian] Login successful"
else
    echo "[obsidian] ERROR: No credentials provided."
    echo "[obsidian] Provide either obsidian_auth_token or obsidian_email + obsidian_password secrets."
    echo "[obsidian] Or log in manually: docker compose exec obsidian-sync ob login"
    exit 1
fi

# ── Vault setup ─────────────────────────────────────────────────────────────
VAULT_NAME="${OBSIDIAN_VAULT_NAME:?OBSIDIAN_VAULT_NAME environment variable is required}"

echo "[obsidian] Setting up vault: ${VAULT_NAME}"
ob sync-setup --vault "$VAULT_NAME" --path /vault 2>/dev/null || {
    echo "[obsidian] Vault already configured or setup failed, continuing..."
}

# ── Start continuous sync ───────────────────────────────────────────────────
# NOTE: If your vault uses end-to-end encryption, ob sync-setup will prompt
# for the encryption password interactively.  Run setup manually once:
#   docker compose exec obsidian-sync ob sync-setup --vault "Name" --path /vault
# The session is persisted in the obsidian-config volume.
echo "[obsidian] Starting continuous sync for vault: ${VAULT_NAME}"
exec ob sync --continuous
