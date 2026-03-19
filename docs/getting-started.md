# Getting Started

SuperMD converts Supernote handwritten notes (`.note`, `.spd`, PDF, PNG) into Markdown using an LLM. You can run it natively (Python) or via Docker.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| An **LLM API key** | Required. OpenAI, Google Gemini, or Anthropic |
| Python ≥ 3.11 | Native install only |
| [uv](https://docs.astral.sh/uv/) | Recommended for native install |
| Docker + Docker Compose v2 | Docker install only |

The default model is `gpt-4o-mini`, which requires an OpenAI API key. Any model in the [llm plugin ecosystem](https://llm.datasette.io/en/stable/plugins/index.html) works.

---

## Option A — Native (Python)

### 1. Clone and install

```bash
git clone https://github.com/rephlex00/SuperMD.git
cd SuperMD

# With uv (recommended)
uv sync

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Set your API key

```bash
# OpenAI (default model)
llm keys set openai

# Or use an environment variable
export OPENAI_API_KEY="sk-..."
```

For other providers, install the matching plugin first:

```bash
llm install llm-gemini    # Google Gemini
llm install llm-claude-3  # Anthropic Claude
```

### 3. Create a config

```bash
cp config/supermd.example.yaml config/supermd.yaml
```

Edit `config/supermd.yaml` and set your `jobs` (input/output directory pairs). See [configuration.md](configuration.md) for all options.

### 4. Run

```bash
# Convert a single file
supermd file path/to/note.note -o ./output

# Convert a directory
supermd directory path/to/notes/ -o ./output

# Run all jobs in config
supermd run --config config/supermd.yaml

# Watch for changes (continuous)
supermd watch --config config/supermd.yaml
```

---

## Option B — Docker (standalone)

The standalone container runs SuperMD only. You supply `.note` files via a bind mount.

See [running-docker.md](running-docker.md) for full instructions.

**Quick version:**

```bash
# Create your config
cp config/supermd.example.yaml config/supermd.yaml

# Copy and edit the .env file
cp .env.example .env

# Start
docker compose up -d
```

---

## Option C — Docker Full Stack

The full stack automates the entire pipeline: Supernote Cloud → SuperMD → Obsidian Sync.

See [docker-stack.md](docker-stack.md) and [`docker/stack/README.md`](../docker/stack/README.md) for full instructions.

**Quick version:**

```bash
cd docker/stack
docker compose run --rm setup         # interactive wizard creates secrets + .env

docker compose --profile cloud up -d  # with Supernote Cloud
docker compose up -d                  # without Supernote Cloud
```

---

## Next steps

- [commands.md](commands.md) — Full CLI reference
- [configuration.md](configuration.md) — All config options
- [templates.md](templates.md) — Jinja2 templates and DATE tokens
- [docker-stack.md](docker-stack.md) — Full stack Docker setup
