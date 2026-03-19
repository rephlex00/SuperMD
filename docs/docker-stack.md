# Docker Full Stack

The full stack deployment automates the entire Supernote-to-Obsidian pipeline using Docker Compose with three services:

1. **supernote-sync** — Downloads `.note` files from Supernote Cloud (optional)
2. **supermd** — Converts handwritten notes to Markdown via LLM
3. **obsidian-sync** — Syncs the output vault to Obsidian Sync

An interactive setup wizard handles secrets and `.env` creation:

```bash
cd docker/stack
docker compose run --rm setup      # or ./setup.sh if running outside Docker
```

All configuration and setup documentation lives in [`docker/stack/README.md`](../docker/stack/README.md).

## Comparison with Standalone Docker

| Feature | Standalone (`docker-compose.yml`) | Full Stack (`docker/stack/`) |
|---------|-----------------------------------|------------------------------|
| SuperMD conversion | Yes | Yes |
| Supernote Cloud sync | No (mount files yourself) | Yes (optional) |
| Obsidian Sync | No (manual) | Yes (automatic) |
| Secrets management | `.env` file | Docker Compose secrets |
| Services | 1 | 3 |

## Architecture

```
Supernote Cloud ──▶ supernote-sync ──▶ supermd ──▶ obsidian-sync ──▶ Obsidian Sync
                     (sncloud)         (watch)     (ob sync)
                    [optional]
```

Data flows through Docker named volumes:
- `notes-data` — Supernote files (supernote-sync writes, supermd reads)
- `vault-data` — Markdown output (supermd writes, obsidian-sync syncs)

## Secrets

Credentials are stored as individual files in `docker/stack/secrets/` and mounted via Docker Compose secrets at `/run/secrets/` inside containers. This keeps passwords out of environment variables and process listings.

Required secrets:

| File | Service | Description |
|------|---------|-------------|
| `llm_api_key` | supermd | OpenAI, Gemini, or Anthropic API key |
| `obsidian_email` | obsidian-sync | Obsidian account email |
| `obsidian_password` | obsidian-sync | Obsidian account password |
| `obsidian_vault_password` | obsidian-sync | E2EE vault encryption password (optional) |
| `supernote_email` | supernote-sync | Supernote Cloud email (cloud profile only) |
| `supernote_password` | supernote-sync | Supernote Cloud password (cloud profile only) |
| `supernote_token` | supernote-sync | Saved JWT access token (cloud profile only, optional) |

## Supernote Cloud Sync

The `supernote-sync` service uses a [fork of sncloud](https://github.com/rnbennett/sncloud) — an unofficial reverse-engineered client for the Supernote Cloud API with CSRF token and OTP verification support. It periodically polls for new `.note` files and downloads them.

New device logins require email OTP verification (E1760 flow). The `setup.sh` wizard handles this interactively and saves the resulting JWT access token to `secrets/supernote_token` for automated restarts.

This service is **optional** and only starts with the `cloud` Docker Compose profile:

```bash
docker compose --profile cloud up -d
```

Users who sync `.note` files via NAS, Dropbox, or other tools can skip this service entirely and bind-mount their files directory instead.

## Obsidian Headless

The `obsidian-sync` service uses the official [obsidian-headless](https://github.com/obsidianmd/obsidian-headless) CLI (released February 2026) to continuously sync the vault with Obsidian Sync.

**Requirements:**
- An Obsidian Sync subscription
- Node.js 22+ (provided by the container)

**Known issues (as of March 2026):**
- The `ob` CLI uses libsecret/gnome-keyring for credential storage, which can fail on headless Linux. The container includes gnome-keyring and D-Bus as a workaround.
- The `OBSIDIAN_AUTH_TOKEN` environment variable is not well documented. If available, it bypasses the keyring entirely.
- If automated login fails, users can log in interactively via `docker compose exec obsidian-sync ob login`.

## Quick Reference

```bash
# Start with Supernote Cloud sync
docker compose --profile cloud up -d

# Start without Supernote Cloud (NAS mount)
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down

# Rebuild after code changes
docker compose --profile cloud build
```

See [`docker/stack/README.md`](../docker/stack/README.md) for complete setup instructions.
