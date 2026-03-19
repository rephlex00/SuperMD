# Running with Docker (Standalone)

The standalone Docker setup runs SuperMD as a single container. You provide `.note` files via a bind mount or volume, and SuperMD converts them to Markdown.

For the full automated pipeline (Supernote Cloud → SuperMD → Obsidian Sync), see [docker-stack.md](docker-stack.md).

---

## Prerequisites

- Docker and Docker Compose v2+
- An LLM API key (OpenAI, Gemini, or Anthropic)

---

## Quick Start

### 1. Configure

```bash
# Copy and edit the SuperMD config
cp config/supermd.example.yaml config/supermd.yaml

# Copy and edit the environment file
cp .env.example .env
```

Edit `.env`:

| Variable | Description |
|---|---|
| `PUID` | Your host user ID (`id -u`) — controls output file ownership |
| `PGID` | Your host group ID (`id -g`) |
| `OPENAI_API_KEY` | Your OpenAI API key (or use `GEMINI_API_KEY` / `ANTHROPIC_API_KEY`) |

### 2. Start

```bash
docker compose up -d
```

The container starts in `watch` mode by default — it monitors the input directory and converts new files automatically.

### 3. Check logs

```bash
docker compose logs -f
```

---

## Configuration

### Bind mounting your notes

The `docker-compose.yml` mounts:

| Container path | Host path | Purpose |
|---|---|---|
| `/input` | *(configure in compose)* | Source `.note` files (read-only) |
| `/output` | *(configure in compose)* | Converted Markdown output |
| `/config/supermd.yaml` | `./config/supermd.yaml` | SuperMD config |

Edit `docker-compose.yml` to point `/input` at your notes directory:

```yaml
services:
  supermd:
    volumes:
      - /path/to/your/notes:/input:ro
      - /path/to/your/vault:/output
      - ./config/supermd.yaml:/config/supermd.yaml:ro
```

### One-shot batch mode

To run a single batch instead of watching continuously, override the command:

```bash
docker compose run --rm supermd run
```

Or set the default command in `docker-compose.yml`:

```yaml
services:
  supermd:
    command: run
```

---

## API Keys

API keys are passed via environment variables in `.env`. Supported variables:

| Variable | Provider |
|---|---|
| `OPENAI_API_KEY` | OpenAI (gpt-4o-mini, gpt-4o, …) |
| `GEMINI_API_KEY` | Google Gemini |
| `ANTHROPIC_API_KEY` | Anthropic Claude |

Set whichever matches the `model` field in your `config/supermd.yaml`.

---

## Building the image

The project includes a multi-stage Dockerfile. To build locally after code changes:

```bash
docker compose build
docker compose up -d
```

---

## File ownership

The container runs as `supermd` (UID 1000 by default). Set `PUID` and `PGID` in `.env` to match your host user so that output files are writable:

```bash
# Find your IDs
id -u   # → PUID
id -g   # → PGID
```

---

## Comparison with full stack

| Feature | Standalone | Full Stack |
|---|---|---|
| SuperMD conversion | Yes | Yes |
| Supernote Cloud download | No (mount files manually) | Yes (optional) |
| Obsidian Sync upload | No | Yes |
| Secrets management | `.env` file | Docker Compose secrets |
| Services | 1 | 3 |

See [docker-stack.md](docker-stack.md) for the full stack.
