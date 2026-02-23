# sn2md

Convert [Supernote](https://supernote.com/) `.note` files (and PDFs, PNGs, and Atelier `.spd` files) into Markdown using an LLM. Designed for syncing handwritten notes into an [Obsidian](https://obsidian.md/) vault.

## Features

- **Multi-format input** — `.note`, `.pdf`, `.png`, `.spd` (Supernote Atelier)
- **LLM-powered transcription** — handwriting → Markdown via any [llm](https://llm.datasette.io/)-compatible model
- **Jinja2 templates** — fully customizable Markdown output
- **Batch jobs** — process multiple input/output folder pairs from a single YAML config
- **File watcher** — auto-convert on file changes with configurable debounce
- **Smart caching** — SHA-1 metadata tracking skips unchanged files and protects hand-edited output
- **Docker-ready** — run as a long-lived container with volume mounts

---

## Prerequisites

| Requirement | Direct Install | Docker |
|---|---|---|
| Python ≥ 3.11 | ✅ Required | — |
| [uv](https://docs.astral.sh/uv/) | ✅ Recommended | — |
| Docker + Compose | — | ✅ Required |
| LLM API key | ✅ Required | ✅ Required |

> **Note:** Any model supported by the [llm](https://llm.datasette.io/en/stable/plugins/index.html) ecosystem works. The default is `gpt-4o-mini` (requires an OpenAI API key).

---

## Quick Start — Direct (Python / uv)

### 1. Clone & install

```bash
git clone https://github.com/your-org/sn2md.git
cd sn2md

# Create venv and install (uv)
uv sync

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure

**Settings** — copy and edit the main config:

```bash
cp config/settings.toml ~/.config/sn2md.toml
```

Key fields in `settings.toml`:

| Field | Description |
|---|---|
| `model` | LLM model name (default: `gpt-4o-mini`) |
| `prompt` | System prompt for page-to-Markdown conversion |
| `template` | Jinja2 template for the final `.md` output |
| `output_path_template` | Directory structure template (e.g. `{{year}}/{{month}}`) |
| `output_filename_template` | Output filename template (e.g. `{{file_basename}}.md`) |

**Jobs** — define input/output folder pairs:

```bash
cp config/jobs.example.yaml config/jobs.local.yaml
```

Edit `config/jobs.local.yaml` to point at your note directories:

```yaml
defaults:
  input: ~/Supernote/Notes
  output: ~/Obsidian/Supernote
  config: ./config/settings.toml
  flags:
    model: gpt-4o-mini
    cooldown: 5.0    # seconds between API calls

jobs:
  - name: Personal
    input: ~/Supernote/Note/Personal
    output: ~/Obsidian/Personal/Supernote
  - name: Work
    input: ~/Supernote/Note/Work
    output: ~/Obsidian/Work/Supernote
```

### 3. Set your API key

```bash
export OPENAI_API_KEY="sk-..."
```

Or place it in a `.env` file referenced by `env_file:` in your jobs config.

### 4. Run

```bash
# Convert a single file
sn2md-cli file path/to/note.note -o ./output

# Convert a directory
sn2md-cli directory path/to/notes/ -o ./output

# Run all configured jobs
sn2md-cli run --config config/jobs.local.yaml

# Watch for changes and auto-convert
sn2md-cli watch --config config/jobs.local.yaml
```

---

## Quick Start — Docker

### 1. Configure environment

```bash
cp example.env .env
```

Edit `.env` and set at minimum:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
PUID=1000
PGID=1000
```

> **Tip:** Run `id` on your host to find your UID/GID. Setting `PUID`/`PGID` ensures output files are owned by your user.

### 2. Prepare directories

```bash
mkdir -p in out
```

Place your `.note` files (or symlink your Supernote sync folder) into `./in/`.

### 3. Build & run

```bash
docker compose up -d
```

This will:
- Build the `sn2md-app` image
- Mount `./in` → `/data/in` (input), `./out` → `/data/out` (output), `./config` → `/config`
- Start the file watcher, which processes new/changed files automatically

### 4. Custom job configuration (optional)

To define multiple jobs or override settings inside the container:

```bash
cp config/jobs.docker.example.yaml config/jobs.yaml
```

Edit `config/jobs.yaml`, then mount it:

```yaml
# docker-compose.yml (already mounts ./config:/config)
# The entrypoint auto-detects /config/jobs.yaml if present.
```

You can also mount a custom `settings.toml`:

```yaml
volumes:
  - ./config/settings.toml:/config/settings.toml
```

And reference it in your `jobs.yaml`:

```yaml
defaults:
  config: /config/settings.toml
```

### 5. View logs

```bash
docker compose logs -f app
```

---

## CLI Reference

```
Usage: sn2md-cli [OPTIONS] COMMAND [ARGS]...

Options:
  -c, --config PATH       Path to sn2md.toml config
  -o, --output PATH       Output directory (default: supernote)
  -f, --force             Force reprocessing of unchanged files
  --progress/--no-progress  Show progress bar (default: on)
  -l, --level TEXT        Log level: DEBUG, INFO, WARNING, ERROR
  -m, --model TEXT        LLM model override
  -v, --version           Show version
```

| Command | Description |
|---|---|
| `file <path>` | Convert a single file |
| `directory <path>` | Convert all supported files in a directory |
| `run` | Run batch jobs from a YAML config |
| `watch` | Watch input directories and auto-convert on changes |
| `meta list` | List tracked files and their status |
| `meta rebuild` | Rebuild metadata from existing input/output pairs |
| `meta rm` | Remove all metadata (reset tracking) |
| `service install` | Install as a macOS launchd service |
| `service uninstall` | Remove the launchd service |
| `service start/stop` | Start or stop the service |
| `service logs` | View service log output |

---

## Template Variables

The following variables are available in both `output_path_template`, `output_filename_template`, and the main `template`:

| Variable | Example | Description |
|---|---|---|
| `file_basename` | `20250104_080151` | Input filename without extension |
| `file_name` | `/path/to/file.note` | Full input path |
| `year_month_day` | `2025-01-04` | Creation date (YYYY-MM-DD) |
| `year` | `2025` | 4-digit year |
| `month` | `Jan` | Abbreviated month |
| `day` | `04` | Zero-padded day |
| `format_date(fmt)` | `format_date('YYYY-MM-DD')` | Obsidian-style date formatting |
| `llm_output` | *(markdown text)* | The LLM transcription |
| `images` | *(list)* | Extracted page images with `.name`, `.link`, `.rel_path` |
| `links` | *(list)* | Notebook internal links |
| `keywords` | *(list)* | Notebook keywords |
| `titles` | *(list)* | Notebook title annotations |

---

## Development

### Install with test dependencies

```bash
uv sync --extra test
# or
pip install -e ".[test]"
```

### Run tests

```bash
python -m pytest tests/ -v
```

### Project structure

```
src/sn2md/
├── cli.py           # Click CLI entry point
├── converter.py     # Core conversion pipeline
├── batches.py       # Multi-job batch runner
├── watcher.py       # File system watcher (watchdog)
├── context.py       # Jinja2 template context builder
├── ai_utils.py      # LLM integration (llm library)
├── metadata_db.py   # SQLite metadata tracking
├── job_config.py    # YAML job config loader
├── service.py       # macOS launchd service management
├── types.py         # Config dataclass & extractor ABC
├── console.py       # Styled console output
├── report.py        # Metadata report printer
├── date_utils.py    # Obsidian-style date formatting
├── utils.py         # Hashing & path utilities
├── importers/
│   ├── note.py      # Supernote .note extractor
│   ├── pdf.py       # PDF extractor (PyMuPDF)
│   ├── png.py       # PNG passthrough extractor
│   └── atelier.py   # Supernote Atelier .spd extractor
└── supernotelib/    # Vendored Supernote parsing library
```

---

## License

Apache-2.0
