# SuperMD Full Stack

Automated pipeline: **Supernote Cloud → SuperMD → Obsidian Sync**

```
┌──────────────────┐      ┌──────────────┐      ┌──────────────────┐
│ supernote-sync   │─────▶│   supermd    │─────▶│  obsidian-sync   │
│ (optional)       │      │              │      │                  │
└──────────────────┘      └──────────────┘      └──────────────────┘
   Supernote Cloud         .note → Markdown       Vault → Obsidian Sync
```

## Prerequisites

- **Docker** and **Docker Compose** v2+
- An **LLM API key** (OpenAI, Google Gemini, or Anthropic)
- An **[Obsidian Sync](https://obsidian.md/sync)** subscription
- *(Optional)* A **Supernote Cloud** account (if using cloud sync)

## Quick Start

### 1. Run the setup wizard

The interactive setup wizard creates secret files, the `.env` configuration, and optionally tests your credentials (including Supernote Cloud OTP verification).

```bash
cd docker/stack
docker compose run --rm setup
# or run directly: ./setup.sh
```

To reset all secrets and `.env`:
```bash
docker compose run --rm setup --reset
```

<details>
<summary>Manual setup (without the wizard)</summary>

```bash
./init-secrets.sh                     # create placeholder files
echo -n "sk-..." > secrets/llm_api_key
echo -n "you@example.com" > secrets/obsidian_email
echo -n "your-password" > secrets/obsidian_password
# Optional (cloud profile only):
echo -n "you@example.com" > secrets/supernote_email
echo -n "your-password" > secrets/supernote_password
cp .env.example .env                  # then edit LLM_PROVIDER, OBSIDIAN_VAULT_NAME, PUID, PGID
```

> **Tip:** Use `echo -n` (no trailing newline) to avoid whitespace issues.

</details>

### 2. Start the stack

**With Supernote Cloud sync:**
```bash
docker compose --profile cloud up -d
```

**Without Supernote Cloud** (mount your own .note files):
```bash
docker compose up -d
```

## NAS / External Sync

If your `.note` files are already synced to a local directory (NAS, Dropbox, iCloud, etc.), skip the Supernote Cloud service and bind-mount your directory instead.

Create `docker-compose.override.yml`:

```yaml
services:
  supermd:
    volumes:
      - /path/to/your/notes:/input:ro
      - vault-data:/output
      - ${SUPERMD_CONFIG:-./supermd.stack.yaml}:/config/supermd.yaml:ro
      - ./supermd-entrypoint.sh:/supermd-entrypoint.sh:ro
```

Then start without the cloud profile:
```bash
docker compose up -d
```

## Custom SuperMD Configuration

The default `supermd.stack.yaml` works out of the box. To customize:

1. Copy `supermd.stack.yaml` to a new file (e.g., `my-config.yaml`)
2. Edit it (see `config/supermd.example.yaml` for all options)
3. Set in `.env`: `SUPERMD_CONFIG=./my-config.yaml`

## Logs

```bash
# All services
docker compose logs -f

# Individual services
docker compose logs -f supernote-sync
docker compose logs -f supermd
docker compose logs -f obsidian-sync
```

## Troubleshooting

### Obsidian login fails (keychain error)

The `obsidian-headless` CLI requires a keychain on Linux. The container includes gnome-keyring as a workaround, but this may fail on some configurations.

**Fallback — interactive login:**
```bash
docker compose exec obsidian-sync ob login
```

Credentials are persisted in the `obsidian-config` volume and survive container restarts.

**Alternative — auth token:**

If Obsidian provides an `OBSIDIAN_AUTH_TOKEN` (check [Obsidian docs](https://help.obsidian.md/headless)):
```bash
echo -n "your-token" > secrets/obsidian_auth_token
```

The token secret is already wired into the compose file — filling in the placeholder file is all that's needed.

### Supernote Cloud sync not downloading files

- Check credentials: `docker compose logs supernote-sync`
- Verify `SYNC_PATH` in `.env` matches your Supernote Cloud folder structure
- The `sncloud` library is unofficial — if Supernote changes their API, sync may break. Use the NAS mount fallback as an alternative.

### SuperMD not processing files

- Verify the API key is correct: `docker compose logs supermd`
- Ensure `LLM_PROVIDER` in `.env` matches the key in `secrets/llm_api_key`
- Check that files appear in the input volume: `docker compose exec supermd ls /input`

## Data Persistence

| Volume | Purpose | Warning |
|--------|---------|---------|
| `notes-data` | Downloaded .note files | Lost on `docker compose down -v` |
| `vault-data` | Converted Markdown + images | Lost on `docker compose down -v` |
| `obsidian-config` | Obsidian login credentials | Lost on `docker compose down -v` |

For production use, consider bind mounts instead of named volumes.

## Architecture

- **supernote-sync** — Python container using a [fork of sncloud](https://github.com/rnbennett/sncloud) (unofficial Supernote Cloud API with CSRF + OTP support). Periodically polls for new `.note` files. New device logins require email OTP verification; the setup wizard handles this and saves a JWT token to `secrets/supernote_token`.
- **supermd** — Existing SuperMD container in watch mode. Converts `.note` → Markdown via LLM.
- **obsidian-sync** — Node.js container running [obsidian-headless](https://github.com/obsidianmd/obsidian-headless) (official). Continuously syncs the vault bidirectionally with Obsidian Sync.
