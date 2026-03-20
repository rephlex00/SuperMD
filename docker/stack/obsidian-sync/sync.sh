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

    # D-Bus + gnome-keyring are started by entrypoint.sh and shared with exec sessions.

    # Skip login if a valid session already exists (e.g. after manual auth).
    if ob sync-list-remote >/dev/null 2>&1; then
        echo "[obsidian] Already authenticated, skipping login"
    else
        ob login --email "$OB_EMAIL" --password "$OB_PASSWORD" || {
            echo "[obsidian] WARNING: automated login failed (2FA required?)."
            echo "[obsidian] Log in manually in another terminal:"
            echo "[obsidian]   docker compose exec -u obsidian obsidian-sync sh -c '. ~/.dbus-env && ob login'"
            echo "[obsidian] Waiting for authentication..."
            until ob sync-list-remote >/dev/null 2>&1; do
                sleep 15
            done
            echo "[obsidian] Authentication detected, continuing..."
        }
        echo "[obsidian] Login successful"
    fi
else
    echo "[obsidian] ERROR: No credentials provided."
    echo "[obsidian] Provide either obsidian_auth_token or obsidian_email + obsidian_password secrets."
    echo "[obsidian] Or log in manually: docker compose exec obsidian-sync ob login"
    exit 1
fi

# ── Vault setup ─────────────────────────────────────────────────────────────
VAULT_NAME="${OBSIDIAN_VAULT_NAME:?OBSIDIAN_VAULT_NAME environment variable is required}"
VAULT_PASSWORD=$(read_secret "obsidian_vault_password")

echo "[obsidian] Setting up vault: ${VAULT_NAME}"

# Build the sync-setup command with optional E2E password.
SETUP_CMD="ob sync-setup --vault \"$VAULT_NAME\" --path /vault"
if [ -n "$VAULT_PASSWORD" ]; then
    echo "[obsidian] E2E vault password provided"
    SETUP_CMD="$SETUP_CMD --password \"$VAULT_PASSWORD\""
fi

eval "$SETUP_CMD" 2>&1 || {
    echo "[obsidian] Vault already configured or setup failed, continuing..."
    echo "[obsidian] If E2E encrypted, provide the password in secrets/obsidian_vault_password"
    echo "[obsidian] or run manually:"
    echo "[obsidian]   docker compose exec -u obsidian obsidian-sync ob sync-setup --vault \"$VAULT_NAME\" --path /vault"
}

# ── Start continuous sync ───────────────────────────────────────────────────
echo "[obsidian] Starting continuous sync for vault: ${VAULT_NAME}"
ob sync --path /vault --continuous 2>&1 | grep -v "Fully Synced"
