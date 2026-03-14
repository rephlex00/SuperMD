#!/bin/sh
# =============================================================================
# init-secrets.sh — Initialise the secrets/ directory before first use.
# =============================================================================
# Creates empty placeholder files for optional secrets so that Docker Compose
# can start without errors even when those features are not configured.
# Required secrets (llm_api_key, obsidian_email, obsidian_password) are NOT
# created here — they must be filled in by the user.
# =============================================================================
set -e

SECRETS_DIR="$(dirname "$0")/secrets"
mkdir -p "$SECRETS_DIR"

create_if_missing() {
    if [ ! -f "$SECRETS_DIR/$1" ]; then
        touch "$SECRETS_DIR/$1"
        echo "  created (empty): secrets/$1"
    else
        echo "  exists:          secrets/$1"
    fi
}

echo "Initialising secret placeholders..."

# Optional: Obsidian auth token.  Leave empty to use email/password login.
create_if_missing obsidian_auth_token

# Cloud profile only: Supernote Cloud credentials.
# Leave empty if you mount .note files from a NAS or local directory instead.
create_if_missing supernote_email
create_if_missing supernote_password

echo ""
echo "Now fill in the REQUIRED secrets (these must not be empty):"
echo "  echo -n 'your-key'      > secrets/llm_api_key"
echo "  echo -n 'you@example'   > secrets/obsidian_email"
echo "  echo -n 'your-password' > secrets/obsidian_password"
echo ""
echo "Then copy and edit the environment file:"
echo "  cp .env.example .env"
