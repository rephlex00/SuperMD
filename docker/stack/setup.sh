#!/usr/bin/env bash
# =============================================================================
# setup.sh — Interactive first-time setup for the SuperMD full stack
# =============================================================================
# Guides you through creating secrets/ files and the .env file, then
# optionally tests Obsidian authentication and generates an auth token.
#
# Usage:
#   ./setup.sh               (run directly — can also test auth)
#   ./setup.sh --reset       (clear all secrets and .env)
#
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SECRETS_DIR="$SCRIPT_DIR/secrets"
ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"

# ── Helpers ──────────────────────────────────────────────────────────────────

bold()  { printf '\033[1m%s\033[0m' "$*"; }
cyan()  { printf '\033[36m%s\033[0m' "$*"; }
green() { printf '\033[32m%s\033[0m' "$*"; }
yellow(){ printf '\033[33m%s\033[0m' "$*"; }
red()   { printf '\033[31m%s\033[0m' "$*"; }
dim()   { printf '\033[2m%s\033[0m' "$*"; }
lc()    { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

header() {
    echo
    echo "$(bold "── $1 ──────────────────────────────────────────────────────────────────")"
    echo
}

info()  { echo "  $(cyan "▸") $*"; }
warn()  { echo "  $(yellow "⚠") $*"; }
ok()    { echo "  $(green "✓") $*"; }
fail()  { echo "  $(red "✗") $*"; }

# Prompt for a secret value and write it to secrets/<name>.
# Usage: prompt_secret <filename> <display_name> <description> <required: yes|no> [mask: yes|no]
prompt_secret() {
    local file="$1" display="$2" desc="$3" required="$4" mask="${5:-yes}"
    local path="$SECRETS_DIR/$file"
    local current=""

    if [ -f "$path" ] && [ -s "$path" ]; then
        if [ "$mask" = "yes" ]; then
            current="$(dim "(already set — press Enter to keep)")"
        else
            current="$(dim "(current: $(cat "$path") — press Enter to keep)")"
        fi
    fi

    echo "$(cyan "$display")"
    echo "  $desc"
    if [ "$required" = "no" ]; then
        echo "  $(dim "Optional — press Enter to skip.")"
    fi
    [ -n "$current" ] && echo "  $current"

    local value
    if [ "$mask" = "yes" ]; then
        read -r -s -p "  > " value
        echo  # newline after silent input
    else
        read -r -p "  > " value
    fi

    if [ -z "$value" ]; then
        if [ -f "$path" ] && [ -s "$path" ]; then
            echo "  $(green "Kept existing value.")"
        elif [ "$required" = "yes" ]; then
            echo "  $(red "This field is required. Please re-run setup and provide a value.")"
            exit 1
        else
            # Ensure an empty placeholder exists so Docker Compose is happy
            touch "$path"
            echo "  $(dim "Skipped (empty placeholder written).")"
        fi
    else
        printf '%s' "$value" > "$path"
        chmod 600 "$path"
        echo "  $(green "Saved.")"
    fi
    echo
}

# Prompt for an .env variable value.
# Usage: prompt_env <var_name> <display_name> <description> <default>
prompt_env() {
    local var="$1" display="$2" desc="$3" default="$4"
    local current_val=""

    # Read existing value from .env if present
    if [ -f "$ENV_FILE" ]; then
        current_val="$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
    fi

    local hint
    if [ -n "$current_val" ]; then
        hint="$(dim "current: $current_val — press Enter to keep")"
    else
        hint="$(dim "default: $default")"
    fi

    echo "$(cyan "$var")"
    echo "  $desc"
    echo "  $hint"
    read -r -p "  > " value
    echo

    if [ -z "$value" ]; then
        value="${current_val:-$default}"
    fi

    # Write or update the variable in .env
    if grep -qE "^${var}=" "$ENV_FILE" 2>/dev/null; then
        # Replace existing line (portable sed)
        local tmpfile
        tmpfile="$(mktemp)"
        sed "s|^${var}=.*|${var}=${value}|" "$ENV_FILE" > "$tmpfile" && mv "$tmpfile" "$ENV_FILE"
    else
        echo "${var}=${value}" >> "$ENV_FILE"
    fi
}

# Read a secret file, return empty string if missing/empty.
read_secret() {
    local path="$SECRETS_DIR/$1"
    if [ -f "$path" ] && [ -s "$path" ]; then
        cat "$path" | tr -d '\n'
    fi
}

# ── Reset flag ────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--reset" ]]; then
    clear
    echo "$(bold "SuperMD Full Stack — Reset")"
    echo
    echo "This will delete all secrets and the .env file, returning the stack"
    echo "to its unconfigured state.  The stack must be stopped first."
    echo
    read -r -p "  Are you sure? [y/N] " CONFIRM
    echo
    if [[ "$(lc "$CONFIRM")" != "y" ]]; then
        echo "  Aborted."
        exit 0
    fi
    rm -f \
        "$SECRETS_DIR/llm_api_key" \
        "$SECRETS_DIR/obsidian_email" \
        "$SECRETS_DIR/obsidian_password" \
        "$SECRETS_DIR/obsidian_auth_token" \
        "$SECRETS_DIR/obsidian_vault_password" \
        "$SECRETS_DIR/supernote_email" \
        "$SECRETS_DIR/supernote_password" \
        "$SECRETS_DIR/supernote_token" \
        "$ENV_FILE"
    echo "  $(green "Secrets and .env removed.")"
    echo "  Run $(bold "./setup.sh") to reconfigure."
    echo
    exit 0
fi

# ── Banner ────────────────────────────────────────────────────────────────────

clear
echo "$(bold "SuperMD Full Stack — Interactive Setup")"
echo "$(dim "Configures secrets/ and .env for docker compose.")"
echo "$(dim "Run from: $SCRIPT_DIR")"

# ── Preflight ─────────────────────────────────────────────────────────────────

mkdir -p "$SECRETS_DIR"

# Ensure all secret files referenced by docker-compose.yml exist (even if empty)
# so that Docker Compose doesn't fail with "bind source path does not exist".
for _secret in llm_api_key obsidian_email obsidian_password \
               obsidian_auth_token obsidian_vault_password \
               supernote_email supernote_password supernote_token; do
    [ -f "$SECRETS_DIR/$_secret" ] || touch "$SECRETS_DIR/$_secret"
done

# Seed .env from example if it doesn't exist yet
if [ ! -f "$ENV_FILE" ] && [ -f "$ENV_EXAMPLE" ]; then
    # Strip comment-only lines so we start with a clean writable file
    grep -vE '^\s*#' "$ENV_EXAMPLE" | grep -vE '^\s*$' > "$ENV_FILE" || true
fi
touch "$ENV_FILE"

# ── Section 1: LLM Provider ─────────────────────────────────────────────────

header "1 / 5  LLM Provider"

echo "$(cyan "LLM_PROVIDER")"
echo "  Which AI provider will transcribe your notes?"
echo "  $(dim "Options: openai | gemini | anthropic")"
echo "  $(dim "Make sure the matching llm plugin is installed in the SuperMD image.")"

current_provider=""
if [ -f "$ENV_FILE" ]; then
    current_provider="$(grep -E '^LLM_PROVIDER=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
fi
[ -n "$current_provider" ] && echo "  $(dim "current: $current_provider — press Enter to keep")" || echo "  $(dim "default: openai")"
read -r -p "  > " LLM_PROVIDER_VAL
echo

LLM_PROVIDER_VAL="${LLM_PROVIDER_VAL:-${current_provider:-openai}}"

if grep -qE '^LLM_PROVIDER=' "$ENV_FILE" 2>/dev/null; then
    tmpfile="$(mktemp)"
    sed "s|^LLM_PROVIDER=.*|LLM_PROVIDER=${LLM_PROVIDER_VAL}|" "$ENV_FILE" > "$tmpfile" && mv "$tmpfile" "$ENV_FILE"
else
    echo "LLM_PROVIDER=${LLM_PROVIDER_VAL}" >> "$ENV_FILE"
fi

case "$LLM_PROVIDER_VAL" in
    openai)    KEY_HINT="sk-..."         ;;
    gemini)    KEY_HINT="AIza..."        ;;
    anthropic) KEY_HINT="sk-ant-..."     ;;
    *)         KEY_HINT="your API key"   ;;
esac

prompt_secret "llm_api_key" \
    "LLM API Key  (secrets/llm_api_key)" \
    "API key for $LLM_PROVIDER_VAL. Looks like: $KEY_HINT" \
    "yes"

# ── Section 2: Obsidian Sync ────────────────────────────────────────────────

header "2 / 5  Obsidian Sync"

echo "  The obsidian-sync service pushes converted notes to your Obsidian vault"
echo "  via Obsidian Sync.  You need an active Obsidian Sync subscription."
echo
echo "  $(bold "Authentication options:")"
echo "    $(cyan "1.") $(bold "Auth token") $(green "(recommended)") — generated by logging in once."
echo "       No 2FA prompt on restarts. Survives container rebuilds."
echo "    $(cyan "2.") $(bold "Email + password") — automated login on each start."
echo "       $(yellow "Will NOT work if 2FA is enabled on your Obsidian account.")"
echo "       If 2FA is on, you must use option 1 (auth token) instead."
echo
echo "  $(dim "If you have 2FA enabled, choose option 1. Setup will build the")"
echo "  $(dim "obsidian-sync image and walk you through a one-time interactive login")"
echo "  $(dim "to generate the token.")"
echo

prompt_env "OBSIDIAN_VAULT_NAME" \
    "Obsidian Vault Name" \
    "Name of the remote vault on your Obsidian Sync account (case-sensitive)." \
    "MyVault"

# Always collect email/password (needed for token generation too)
prompt_secret "obsidian_email" \
    "Obsidian account email  (secrets/obsidian_email)" \
    "Email address for your obsidian.md account." \
    "yes" "no"

prompt_secret "obsidian_password" \
    "Obsidian account password  (secrets/obsidian_password)" \
    "Password for your obsidian.md account." \
    "yes"

# Check if auth token already exists
EXISTING_TOKEN="$(read_secret "obsidian_auth_token")"

if [ -n "$EXISTING_TOKEN" ]; then
    info "An auth token already exists in secrets/obsidian_auth_token."
    echo
    read -r -p "  Keep existing token? [Y/n] " KEEP_TOKEN
    echo
    if [[ "$(lc "$KEEP_TOKEN")" == "n" ]]; then
        EXISTING_TOKEN=""
        : > "$SECRETS_DIR/obsidian_auth_token"
    else
        ok "Keeping existing auth token."
        echo
    fi
fi

if [ -z "$EXISTING_TOKEN" ]; then
    echo "  $(cyan "How would you like to authenticate?")"
    echo "    $(bold "1.") Generate auth token now $(green "(recommended, works with 2FA)")"
    echo "    $(bold "2.") Use email/password only $(yellow "(fails if 2FA is enabled)")"
    echo "    $(bold "3.") Skip — I'll configure auth later"
    echo
    read -r -p "  Choice [1/2/3]: " AUTH_CHOICE
    echo

    case "${AUTH_CHOICE:-1}" in
        1)
            # ── Generate auth token via obsidian-sync container ──────────
            info "Building obsidian-sync image (this may take a minute on first run)..."
            echo
            if ! docker compose build obsidian-sync > /dev/null 2>&1; then
                fail "Failed to build obsidian-sync image."
                warn "You can generate the token manually later:"
                echo "    docker compose run --rm --entrypoint /entrypoint.sh obsidian-sync \\"
                echo "      sh -c 'ob login && cat ~/.config/obsidian-headless/auth_token'"
                echo
                touch "$SECRETS_DIR/obsidian_auth_token"
            else
                ok "Image built."
                echo
                info "Starting interactive login inside the obsidian-sync container."
                info "You will be prompted for your email, password, and 2FA code (if enabled)."
                echo
                echo "  $(dim "────────────────────────────────────────────────────────")"

                local_email="$(read_secret "obsidian_email")"
                local_password="$(read_secret "obsidian_password")"

                # Run login interactively — stdin/stdout stay connected to the
                # terminal so the user can enter the 2FA code when prompted.
                # The token is extracted from the config volume afterward.
                if docker compose run --rm \
                    -v stack_obsidian-config:/home/obsidian/.config \
                    --entrypoint /entrypoint.sh \
                    obsidian-sync \
                    ob login --email "$local_email" --password "$local_password"; then

                    echo "  $(dim "────────────────────────────────────────────────────────")"
                    echo

                    # Extract token from the config volume
                    GENERATED_TOKEN=$(docker run --rm \
                        -v stack_obsidian-config:/cfg alpine \
                        cat /cfg/obsidian-headless/auth_token 2>/dev/null) || true

                    if [ -n "$GENERATED_TOKEN" ]; then
                        printf '%s' "$GENERATED_TOKEN" > "$SECRETS_DIR/obsidian_auth_token"
                        chmod 600 "$SECRETS_DIR/obsidian_auth_token"
                        ok "Auth token generated and saved to secrets/obsidian_auth_token."
                        info "This token bypasses email/password/2FA on all future starts."
                    else
                        warn "Login succeeded but could not extract token automatically."
                        warn "You can extract it manually from the obsidian-config volume:"
                        echo "    docker run --rm -v stack_obsidian-config:/cfg alpine \\"
                        echo "      cat /cfg/obsidian-headless/auth_token"
                        touch "$SECRETS_DIR/obsidian_auth_token"
                    fi
                else
                    echo "  $(dim "────────────────────────────────────────────────────────")"
                    echo
                    fail "Login failed. This can happen if:"
                    echo "    - Email/password are incorrect"
                    echo "    - 2FA code was wrong or expired"
                    echo "    - Network connectivity issue"
                    echo
                    warn "You can retry by re-running ./setup.sh, or generate the token manually:"
                    echo "    docker compose run --rm --entrypoint /entrypoint.sh obsidian-sync \\"
                    echo "      sh -c 'ob login && cat ~/.config/obsidian-headless/auth_token'"
                    touch "$SECRETS_DIR/obsidian_auth_token"
                fi
                echo
            fi
            ;;
        2)
            # ── Email/password only ──────────────────────────────────────
            echo "  $(yellow "Important:") If 2FA is enabled on your Obsidian account, email/password"
            echo "  login will $(bold "fail") on every container start. The container will wait for"
            echo "  manual login, which defeats the purpose of automation."
            echo
            echo "  $(dim "To switch to token auth later, run:")"
            echo "    docker compose exec -u obsidian obsidian-sync \\"
            echo "      sh -c '. ~/.dbus-env && ob login'"
            echo "    docker run --rm -v stack_obsidian-config:/cfg alpine \\"
            echo "      cat /cfg/obsidian-headless/auth_token"
            echo "  $(dim "Then paste the token into secrets/obsidian_auth_token.")"
            echo

            # Test if login works (will prompt for 2FA if required)
            read -r -p "  Test login now? (builds image, attempts login) [y/N] " TEST_LOGIN
            echo
            if [[ "$(lc "$TEST_LOGIN")" == "y" ]]; then
                info "Building obsidian-sync image..."
                if docker compose build obsidian-sync > /dev/null 2>&1; then
                    ok "Image built."
                    local_email="$(read_secret "obsidian_email")"
                    local_password="$(read_secret "obsidian_password")"
                    info "Testing login (if 2FA is enabled you'll be prompted)..."
                    echo "  $(dim "────────────────────────────────────────────────────────")"

                    if docker compose run --rm \
                        -v stack_obsidian-config:/home/obsidian/.config \
                        --entrypoint /entrypoint.sh \
                        obsidian-sync \
                        ob login --email "$local_email" --password "$local_password"; then

                        echo "  $(dim "────────────────────────────────────────────────────────")"
                        echo
                        ok "Login successful — email/password authentication works."
                        echo "  $(dim "Note: If you enable 2FA later, you'll need to switch to token auth.")"
                        echo
                        echo "  $(cyan "Tip:") Since login worked, you can save the auth token for"
                        echo "  fully automated restarts (no login on each start)."
                        read -r -p "  Save auth token now? [Y/n] " SAVE_TOKEN
                        echo
                        if [[ "$(lc "$SAVE_TOKEN")" != "n" ]]; then
                            GENERATED_TOKEN=$(docker run --rm \
                                -v stack_obsidian-config:/cfg alpine \
                                cat /cfg/obsidian-headless/auth_token 2>/dev/null) || true
                            if [ -n "$GENERATED_TOKEN" ]; then
                                printf '%s' "$GENERATED_TOKEN" > "$SECRETS_DIR/obsidian_auth_token"
                                chmod 600 "$SECRETS_DIR/obsidian_auth_token"
                                ok "Auth token saved to secrets/obsidian_auth_token."
                            else
                                warn "Could not extract token from config volume."
                            fi
                        fi
                    else
                        echo "  $(dim "────────────────────────────────────────────────────────")"
                        echo
                        fail "Login failed. If 2FA was required, consider re-running setup"
                        fail "and choosing option 1 (Generate auth token) instead."
                    fi
                    echo
                else
                    fail "Failed to build obsidian-sync image."
                fi
            fi
            touch "$SECRETS_DIR/obsidian_auth_token"
            ;;
        3)
            info "Skipping auth setup. You'll need to configure authentication before"
            info "starting the obsidian-sync service."
            echo
            touch "$SECRETS_DIR/obsidian_auth_token"
            ;;
    esac
fi

# ── E2E vault encryption password ────────────────────────────────────────────

echo "  $(cyan "Vault encryption")"
echo "  If your Obsidian vault uses end-to-end (E2E) encryption, the encryption"
echo "  password is needed to set up sync. Without it, sync-setup will fail."
echo "  $(dim "Leave blank if your vault uses standard (managed) encryption.")"
echo

EXISTING_VAULT_PW="$(read_secret "obsidian_vault_password")"

if [ -n "$EXISTING_VAULT_PW" ]; then
    info "A vault password already exists."
    read -r -p "  Keep existing vault password? [Y/n] " KEEP_VP
    echo
    if [[ "$(lc "$KEEP_VP")" == "n" ]]; then
        EXISTING_VAULT_PW=""
    else
        ok "Keeping existing vault password."
        echo
    fi
fi

if [ -z "$EXISTING_VAULT_PW" ]; then
    prompt_secret "obsidian_vault_password" \
        "Vault E2E encryption password  (secrets/obsidian_vault_password)" \
        "End-to-end encryption password for your Obsidian vault." \
        "no"
else
    echo
fi

# ── Section 3: Supernote Cloud (optional) ─────────────────────────────────────

header "3 / 5  Supernote Cloud  (optional)"

echo "  Only needed if you want the stack to pull files directly from Supernote"
echo "  Cloud ($(cyan "--profile cloud")).  Skip if you sync .note files via NAS, USB, or"
echo "  another tool — the supermd and obsidian-sync services work without it."
echo

read -r -p "  Configure Supernote Cloud credentials? [y/N] " CLOUD_CHOICE
echo
if [[ "$(lc "$CLOUD_CHOICE")" == "y" ]]; then
    prompt_secret "supernote_email" \
        "Supernote account email  (secrets/supernote_email)" \
        "Email address for your Supernote Cloud account." \
        "no" "no"

    prompt_secret "supernote_password" \
        "Supernote account password  (secrets/supernote_password)" \
        "Password for your Supernote Cloud account." \
        "no"

    prompt_env "SYNC_INTERVAL" \
        "SYNC_INTERVAL" \
        "How often (seconds) to poll Supernote Cloud for new files." \
        "300"

    prompt_env "SYNC_PATH" \
        "SYNC_PATH" \
        "Remote directory on Supernote Cloud to sync from." \
        "/Note"

    # ── Test Supernote Cloud login ──────────────────────────────────────────
    SN_EMAIL="$(read_secret "supernote_email")"
    SN_PASSWORD="$(read_secret "supernote_password")"

    if [ -n "$SN_EMAIL" ] && [ -n "$SN_PASSWORD" ]; then
        echo
        info "Testing Supernote Cloud login..."
        echo
        info "Building supernote-sync image..."
        if ! docker compose --profile cloud build supernote-sync > /dev/null 2>&1; then
            fail "Failed to build supernote-sync image."
            warn "You can test login later when starting the stack."
            echo
        else
            ok "Image built."
            echo

            # Run a login test inside the container. The Python script prints
            # a status line: "OK", "__E1760__:<timestamp>", or "FAIL:<message>".
            LOGIN_RESULT=$(SN_EMAIL="$SN_EMAIL" SN_PASSWORD="$SN_PASSWORD" \
                docker compose run --rm \
                -e SN_EMAIL -e SN_PASSWORD \
                --entrypoint python3 \
                supernote-sync \
                -c "
import os, sys
from sncloud import SNClient
from sncloud.exceptions import AuthenticationError
client = SNClient()
try:
    token = client.login(os.environ['SN_EMAIL'], os.environ['SN_PASSWORD'])
    print('TOKEN:' + token)
except AuthenticationError as e:
    err = str(e)
    if err.startswith('__E1760__:'):
        print(err)
    else:
        print('FAIL:' + err)
except Exception as e:
    print('FAIL:' + str(e))
" 2>/dev/null) || true

            if echo "$LOGIN_RESULT" | grep -q "^TOKEN:"; then
                SN_ACCESS_TOKEN="${LOGIN_RESULT#TOKEN:}"
                printf '%s' "$SN_ACCESS_TOKEN" > "$SECRETS_DIR/supernote_token"
                chmod 600 "$SECRETS_DIR/supernote_token"
                ok "Supernote Cloud login successful! No verification needed."
                info "Access token saved to secrets/supernote_token."
                echo
                SNCLOUD_AUTH="ok"

            elif echo "$LOGIN_RESULT" | grep -q "^__E1760__:"; then
                SN_TIMESTAMP="${LOGIN_RESULT#__E1760__:}"
                echo
                warn "Supernote Cloud requires identity verification (new device)."
                echo "  A 6-digit code will be sent to your email."
                echo
                read -r -p "  Send verification code now? [Y/n] " SN_SEND_OTP
                echo

                if [[ "$(lc "${SN_SEND_OTP:-y}")" != "n" ]]; then
                    # Send the OTP email
                    SEND_RESULT=$(SN_EMAIL="$SN_EMAIL" SN_TIMESTAMP="$SN_TIMESTAMP" \
                        docker compose run --rm \
                        -e SN_EMAIL -e SN_TIMESTAMP \
                        --entrypoint python3 \
                        supernote-sync \
                        -c "
import os, sys
from sncloud import SNClient
from sncloud.exceptions import AuthenticationError
client = SNClient()
try:
    vck = client.send_verification_code(os.environ['SN_EMAIL'], os.environ['SN_TIMESTAMP'])
    print('VCK:' + vck)
except Exception as e:
    print('FAIL:' + str(e))
" 2>/dev/null) || true

                    if echo "$SEND_RESULT" | grep -q "^VCK:"; then
                        SN_VCK="${SEND_RESULT#VCK:}"
                        ok "Verification code sent! Check your email."
                    else
                        # Code may have been sent by the login attempt itself
                        SN_VCK=""
                        warn "Could not send code: ${SEND_RESULT#FAIL:}"
                        info "A code may have already been sent. Check your email."
                    fi
                    echo

                    read -r -p "  Enter the 6-digit code from your email: " SN_OTP_CODE
                    echo

                    if [ -n "$SN_OTP_CODE" ]; then
                        # Verify OTP then immediately login in the same
                        # container/session to get the access token.  The OTP
                        # verification trusts the device so the subsequent
                        # login() succeeds without another E1760.
                        VERIFY_RESULT=$(SN_EMAIL="$SN_EMAIL" SN_PASSWORD="$SN_PASSWORD" \
                            SN_OTP="$SN_OTP_CODE" \
                            SN_VCK="$SN_VCK" SN_TIMESTAMP="$SN_TIMESTAMP" \
                            docker compose run --rm \
                            -e SN_EMAIL -e SN_PASSWORD -e SN_OTP -e SN_VCK -e SN_TIMESTAMP \
                            --entrypoint python3 \
                            supernote-sync \
                            -c "
import os, sys
from sncloud import SNClient
from sncloud.exceptions import AuthenticationError
client = SNClient()
email = os.environ['SN_EMAIL']
password = os.environ['SN_PASSWORD']
# Step 1: verify the OTP to trust this device
try:
    token = client.verify_otp(email, os.environ['SN_OTP'],
                              os.environ['SN_VCK'], os.environ['SN_TIMESTAMP'])
    if token:
        print('TOKEN:' + token)
        sys.exit(0)
except AuthenticationError as e:
    if 'query/token returned no token' not in str(e):
        print('FAIL:' + str(e))
        sys.exit(1)
    # OTP succeeded but no token — fall through to login
except Exception as e:
    print('FAIL:' + str(e))
    sys.exit(1)
# Step 2: device is now trusted — login to get access token
try:
    token = client.login(email, password)
    print('TOKEN:' + token)
except Exception as e:
    print('FAIL:' + str(e))
" 2>/dev/null) || true

                        if echo "$VERIFY_RESULT" | grep -q "^TOKEN:"; then
                            SN_ACCESS_TOKEN="${VERIFY_RESULT#TOKEN:}"
                            printf '%s' "$SN_ACCESS_TOKEN" > "$SECRETS_DIR/supernote_token"
                            chmod 600 "$SECRETS_DIR/supernote_token"
                            ok "Supernote Cloud verification successful!"
                            info "Access token saved to secrets/supernote_token."
                            info "The container will use this token directly — no login needed."
                            echo
                            SNCLOUD_AUTH="ok"
                        else
                            fail "Verification failed: ${VERIFY_RESULT#FAIL:}"
                            warn "You can retry by re-running ./setup.sh"
                            warn "Or provide the code at runtime:"
                            echo "    docker compose exec supernote-sync sh -c 'echo CODE > /otp/code'"
                            echo
                            SNCLOUD_AUTH="fail"
                        fi
                    else
                        warn "No code entered. You can provide it at runtime:"
                        echo "    docker compose exec supernote-sync sh -c 'echo CODE > /otp/code'"
                        echo
                        SNCLOUD_AUTH="skip"
                    fi
                else
                    info "Skipped. The container will prompt for the code at runtime:"
                    echo "    docker compose exec supernote-sync sh -c 'echo CODE > /otp/code'"
                    echo
                    SNCLOUD_AUTH="skip"
                fi

            else
                fail "Supernote Cloud login failed: ${LOGIN_RESULT#FAIL:}"
                warn "Check your email and password in secrets/supernote_email and secrets/supernote_password."
                echo
                SNCLOUD_AUTH="fail"
            fi
        fi
    fi
else
    # Create empty placeholders so Docker Compose can start without errors
    touch "$SECRETS_DIR/supernote_email"
    touch "$SECRETS_DIR/supernote_password"
    echo "  $(dim "Skipped — empty placeholders written for supernote_email / supernote_password.")"
    echo
fi

# ── Section 4: User identity ──────────────────────────────────────────────────

header "4 / 5  User Identity"

echo "  Output files will be owned by this UID/GID on the host.  Run $(cyan "id") in your"
echo "  terminal to find your values (usually 1000 on Linux, varies on macOS)."
echo

HOST_UID="${PUID:-$(id -u)}"
HOST_GID="${PGID:-$(id -g)}"

prompt_env "PUID" \
    "PUID  (host user ID)" \
    "Files in the output volume will be owned by this UID." \
    "$HOST_UID"

prompt_env "PGID" \
    "PGID  (host group ID)" \
    "Files in the output volume will be owned by this GID." \
    "$HOST_GID"

# ── Section 5: Advanced ───────────────────────────────────────────────────────

header "5 / 5  Advanced  (optional)"

echo "  These settings have sensible defaults — skip unless you need to override."
echo

read -r -p "  Configure advanced settings? [y/N] " ADV_CHOICE
echo
if [[ "$(lc "$ADV_CHOICE")" == "y" ]]; then
    prompt_env "SUPERMD_CONFIG" \
        "SUPERMD_CONFIG" \
        "Path to a custom supermd YAML config file (leave blank for the stack default)." \
        ""
fi

# ── Summary ───────────────────────────────────────────────────────────────────

header "Setup complete"

echo "  $(green "secrets/")     — credentials written to $SECRETS_DIR"
echo "  $(green ".env")         — environment written to $ENV_FILE"
echo

# Show auth method summary
AUTH_TOKEN_SET="$(read_secret "obsidian_auth_token")"
VAULT_PW_SET="$(read_secret "obsidian_vault_password")"

echo "$(bold "Obsidian Sync configuration:")"
if [ -n "$AUTH_TOKEN_SET" ]; then
    echo "  $(green "✓") Auth method: $(bold "token") (no login required on start)"
else
    echo "  $(yellow "⚠") Auth method: $(bold "email/password")"
    echo "    If 2FA is enabled, the container will wait for manual login."
    echo "    To generate a token later:"
    echo "      docker compose exec -u obsidian obsidian-sync sh -c '. ~/.dbus-env && ob login'"
    echo "      docker run --rm -v stack_obsidian-config:/cfg alpine cat /cfg/obsidian-headless/auth_token"
    echo "      # Paste the token into secrets/obsidian_auth_token"
fi

if [ -n "$VAULT_PW_SET" ]; then
    echo "  $(green "✓") Vault encryption: $(bold "E2E password set")"
else
    echo "  $(dim "·") Vault encryption: $(bold "standard") (no password needed)"
fi
echo

if [[ "$(lc "$CLOUD_CHOICE")" == "y" ]]; then
    echo "$(bold "Supernote Cloud configuration:")"
    case "${SNCLOUD_AUTH:-skip}" in
        ok)
            echo "  $(green "✓") Login: $(bold "verified") (device trusted, no OTP needed)"
            ;;
        fail)
            echo "  $(red "✗") Login: $(bold "failed") — check credentials or re-run setup"
            ;;
        *)
            echo "  $(yellow "⚠") Login: $(bold "not tested") — the container will attempt login at startup"
            echo "    If a verification code is required:"
            echo "      docker compose exec supernote-sync sh -c 'echo CODE > /otp/code'"
            ;;
    esac
    echo
fi

echo "$(bold "Next steps:")"
echo

if [[ "$(lc "$CLOUD_CHOICE")" == "y" ]]; then
    echo "  $(cyan "With")    Supernote Cloud sync:"
    echo "    docker compose --profile cloud up -d"
else
    echo "  $(cyan "Without") Supernote Cloud sync (mount .note files yourself):"
    echo "    docker compose up -d"
fi

echo
echo "  View logs:  docker compose logs -f"
echo "  Stop:       docker compose down"
echo "  Reset:      ./setup.sh --reset"
echo
