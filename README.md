# SuperMD

Convert [Supernote](https://supernote.com/) `.note` files (and PDFs, PNGs, and Atelier `.spd` files) into Markdown using an LLM. Designed for syncing handwritten notes into an [Obsidian](https://obsidian.md/) vault.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Running the Project](#running-the-project)
- [CLI Reference](#cli-reference)
- [Template Variables](#template-variables)
- [Development](#development)
- [Documentation](#documentation)
- [Acknowledgements](#acknowledgements)

## Features

- **Multi-format input** — `.note`, `.pdf`, `.png`, `.spd` (Supernote Atelier)
- **LLM-powered transcription** — handwriting → Markdown via any [llm](https://llm.datasette.io/)-compatible model
- **Jinja2 templates** — fully customizable Markdown output
- **Batch jobs** — process multiple input/output folder pairs from a single YAML config
- **File watcher** — auto-convert on file changes with configurable debounce
- **Smart caching** — SHA-1 metadata tracking skips unchanged files and protects hand-edited output

---

## Prerequisites

| Requirement | Notes |
|---|---|
| An **LLM API key** | Required — OpenAI, Gemini, or Anthropic |
| Python ≥ 3.11 | Native install only |
| [uv](https://docs.astral.sh/uv/) | Recommended for native install |
| Docker + Compose v2 | Docker install only |

> **Note:** Any model supported by the [llm](https://llm.datasette.io/en/stable/plugins/index.html) ecosystem works. The default is `gpt-4o-mini` (requires an OpenAI API key).

---

## Quick Start

**Native:**

```bash
git clone https://github.com/rephlex00/SuperMD.git && cd SuperMD
uv sync
cp config/supermd.example.yaml config/supermd.yaml
llm keys set openai
supermd watch --config config/supermd.yaml
```

**Docker (standalone):**

```bash
git clone https://github.com/rephlex00/SuperMD.git && cd SuperMD
cp config/supermd.example.yaml config/supermd.yaml
cp .env.example .env  # add OPENAI_API_KEY and set PUID/PGID
docker compose up -d
```

**Docker (full stack — Supernote Cloud → SuperMD → Obsidian Sync):**

```bash
cd docker/stack
docker compose run --rm setup         # interactive wizard creates secrets + .env
docker compose --profile cloud up -d
```

---

## Running the Project

| Mode | Command | Guide |
|---|---|---|
| Native (single file) | `supermd file note.note -o ./output` | [docs/getting-started.md](docs/getting-started.md) |
| Native (watch) | `supermd watch --config config/supermd.yaml` | [docs/getting-started.md](docs/getting-started.md) |
| Docker standalone | `docker compose up -d` | [docs/running-docker.md](docs/running-docker.md) |
| Docker full stack | `docker compose --profile cloud up -d` | [docs/docker-stack.md](docs/docker-stack.md) |

---

## Detailed Setup

### 1. Clone & install

```bash
git clone https://github.com/rephlex00/SuperMD.git
cd SuperMD

# Create venv and install (uv)
uv sync

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure

Copy and edit the example config:

```bash
cp config/supermd.example.yaml config/supermd.yaml
```

Key fields in `supermd.yaml`:

| Field | Description |
|---|---|
| `model` | LLM model name (default: `gpt-4o-mini`) |
| `prompt` | System prompt for page-to-Markdown conversion |
| `template` | Jinja2 template for the final `.md` output |
| `output_path_template` | Directory structure template (e.g. `{{DATE:YYYY/MM MMM}}`) |
| `output_filename_template` | Output filename template (e.g. `{{file_basename}}.md`) |
| `note_title_prompt` | Optional second LLM call to derive a short title for the note |
| `jobs` | List of input/output folder pairs for batch processing |

### 3. Set your API key

```bash
# Option A: store in the llm keystore
llm keys set openai
# or via the supermd CLI
supermd config keys set openai

# Option B: environment variable
export OPENAI_API_KEY="sk-..."
```

Install the matching `llm` plugin if you use a non-OpenAI model:

```bash
llm install llm-gemini    # Google Gemini
llm install llm-claude-3  # Anthropic Claude
```

### 4. Run

```bash
# Convert a single file
supermd file path/to/note.note -o ./output

# Convert a directory
supermd directory path/to/notes/ -o ./output

# Run all configured jobs
supermd run --config config/supermd.yaml

# Watch for changes and auto-convert
supermd watch --config config/supermd.yaml
```

---

## CLI Reference

```
Usage: supermd [OPTIONS] COMMAND [ARGS]...

Options:
  -c, --config PATH         Path to supermd.yaml config (default: config/supermd.yaml)
  -o, --output PATH         Output directory (default: supernote)
  -f, --force               Force reprocessing of unchanged files
  --progress/--no-progress  Show progress bar (default: on)
  -l, --level TEXT          Log level: DEBUG, INFO, WARNING, ERROR
  -m, --model TEXT          LLM model override
  -v, --version             Show version
```

| Command | Description |
|---|---|
| `file <path>` | Convert a single file |
| `directory <path>` | Convert all supported files in a directory |
| `run` | Run batch jobs from a YAML config (`--config`, `--jobs`, `--dry-run`, `--debug`) |
| `watch` | Watch input directories and auto-convert on changes (`--config`, `--jobs`, `--delay`) |
| `meta list` | List tracked files and their status (`--verbose`) |
| `meta rebuild` | Rebuild metadata from existing input/output pairs |
| `meta rm` | Remove all metadata (reset tracking) |
| `config keys set <name>` | Store an API key in the llm keystore |
| `config keys list` | Show configured API keys (keystore + environment) |
| `config keys path` | Show the path to the llm keys file |
| `service install` | Install as a macOS launchd service |
| `service uninstall` | Remove the launchd service |
| `service start` | Start the service |
| `service stop` | Stop the service |
| `service status` | Check status of the background service |
| `service logs` | View service log output (`--lines`, `--follow`) |

---

## Template Variables

The following variables are available in `output_path_template`, `output_filename_template`, and the main `template`:

| Variable | Example | Description |
|---|---|---|
| `file_basename` | `20250104_080151` | Input filename without extension |
| `file_name` | `/path/to/file.note` | Full absolute input path |
| `ctime` | `datetime` | Parsed from filename (`YYYYMMDD_HHMMSS` / `YYYYMMDD`), falls back to filesystem mtime |
| `mtime` | `datetime` | Filesystem modification time |
| `title` | `My Note Title` | LLM-derived title (empty string if `note_title_prompt` is not set) |
| `llm_output` | *(markdown text)* | The full LLM transcription (main `template` only) |
| `images` | *(list)* | Extracted page images — each has `.name`, `.link`, `.rel_path`, `.abs_path` |
| `links` | *(list)* | Notebook cross-references (`.note` only) — each has `.page_number`, `.type`, `.name`, `.inout` |
| `keywords` | *(list)* | Notebook keywords (`.note` only) — each has `.page_number`, `.content` |
| `titles` | *(list)* | Notebook heading metadata (`.note` only) — each has `.page_number`, `.content`, `.level` |

### DATE token expansion

Use `{{DATE:format}}` anywhere in path/filename templates and in the main `template`. The date is sourced from the file's `ctime`.

| Token | Example output | Description |
|---|---|---|
| `YYYY` | `2026` | 4-digit year |
| `YY` | `26` | 2-digit year |
| `MM` | `03` | 2-digit month |
| `MMM` | `Mar` | 3-letter month abbreviation |
| `MMMM` | `March` | Full month name |
| `DD` | `13` | 2-digit day |
| `D` | `13` | Day without padding |
| `HH` | `14` | 2-digit hour (24h) |
| `mm` | `30` | 2-digit minute |
| `ss` | `45` | 2-digit second |
| `dddd` | `Thursday` | Full day name |
| `ddd` | `Thu` | 3-letter day abbreviation |
| `[text]` | `T` | Literal text passthrough |

Examples:

```yaml
output_path_template: "{{DATE:YYYY/MM MMM}}"       # → 2026/03 Mar/
output_filename_template: "{{DATE:YYMMDD}}-{{file_basename}}.md"  # → 260313-20260313_143000.md
```

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
pytest
pytest tests/test_core.py -v         # single file
pytest tests/test_core.py::test_name # single test
```

### Project structure

```
src/supermd/
├── cli.py           # Click CLI entry point
├── converter.py     # Core conversion pipeline
├── batches.py       # Multi-job batch runner
├── watcher.py       # File system watcher (watchdog)
├── context.py       # Jinja2 template context builder
├── ai_utils.py      # LLM integration (llm library)
├── metadata_db.py   # SQLite metadata tracking
├── config.py        # Unified YAML config loader
├── service.py       # macOS launchd service management
├── types.py         # Extractor ABC
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

## Documentation

| Guide | Description |
|---|---|
| [docs/getting-started.md](docs/getting-started.md) | Prerequisites, install, first run (all modes) |
| [docs/running-docker.md](docs/running-docker.md) | Standalone Docker container setup |
| [docs/docker-stack.md](docs/docker-stack.md) | Full 3-service stack (Supernote Cloud → SuperMD → Obsidian Sync) |
| [docs/configuration.md](docs/configuration.md) | All config fields, defaults, environment variables |
| [docs/commands.md](docs/commands.md) | Complete CLI reference |
| [docs/templates.md](docs/templates.md) | Jinja2 template variables and DATE tokens |
| [docker/stack/README.md](docker/stack/README.md) | Full stack setup and troubleshooting |

---

## Acknowledgements

### sn2md

SuperMD is based on [sn2md](https://github.com/dsummersl/sn2md), a Supernote-to-Markdown converter by dsummersl. SuperMD extends that foundation with batch processing, file watching, a macOS launchd service, unified YAML configuration, smart caching, and multi-format input support.

### Vendored packages

SuperMD vendors the following libraries directly into its source tree rather than declaring them as installable dependencies. This avoids version conflicts and ensures compatibility with the specific Supernote file format revisions that SuperMD targets.

| Package | Location | Upstream | Reason for vendoring |
|---|---|---|---|
| `supernotelib` | `src/supermd/supernotelib/` | [jya-dev/supernote-tool](https://github.com/jya-dev/supernote-tool) (Apache-2.0, © 2020 jya) | Vendored to apply patches for blank-image edge cases and to pin to a specific format revision without depending on an upstream release cadence |

### Key Python dependencies

| Package | Purpose | Link |
|---|---|---|
| `llm` | LLM abstraction layer — powers all AI transcription and title generation calls | [llm.datasette.io](https://llm.datasette.io/) |
| `llm-ollama` | Plugin adding local Ollama model support to `llm` | [github.com/taketwo/llm-ollama](https://github.com/taketwo/llm-ollama) |
| `click` | CLI framework | [click.palletsprojects.com](https://click.palletsprojects.com/) |
| `Jinja2` | Template engine for Markdown output | [jinja.palletsprojects.com](https://jinja.palletsprojects.com/) |
| `pydantic` | Config validation and data modelling | [docs.pydantic.dev](https://docs.pydantic.dev/) |
| `PyMuPDF` | PDF page extraction | [pymupdf.readthedocs.io](https://pymupdf.readthedocs.io/) |
| `Pillow` | Image processing and PNG handling | [python-pillow.org](https://python-pillow.org/) |
| `watchdog` | Cross-platform filesystem event monitoring | [github.com/gorakhargosh/watchdog](https://github.com/gorakhargosh/watchdog) |
| `tqdm` | Progress bars | [tqdm.github.io](https://tqdm.github.io/) |
| `PyYAML` | YAML config parsing | [pyyaml.org](https://pyyaml.org/) |
| `pypng` | PNG read/write (used by supernotelib) | [github.com/drj11/pypng](https://github.com/drj11/pypng) |
| `potracer` | Bitmap-to-vector tracing (used by supernotelib) | [github.com/tatarize/potrace](https://github.com/tatarize/potrace) |
| `svgwrite` | SVG generation (used by supernotelib) | [github.com/mozman/svgwrite](https://github.com/mozman/svgwrite) |
| `svglib` | SVG rendering (used by supernotelib) | [github.com/deeplook/svglib](https://github.com/deeplook/svglib) |
| `colour` | Color parsing and conversion (used by supernotelib) | [github.com/vaab/colour](https://github.com/vaab/colour) |
| `platformdirs` | Platform-appropriate data/config directory paths | [github.com/tox-dev/platformdirs](https://github.com/tox-dev/platformdirs) |
| `numpy` | Array operations for image data | [numpy.org](https://numpy.org/) |

### Docker stack components

| Component | Purpose | Link |
|---|---|---|
| `sncloud` (rnbennett fork) | Supernote Cloud API client — used by the `supernote-sync` service to download `.note` files. This fork adds CSRF token handling and OTP/E1760 device-verification support missing from the original. | [github.com/rnbennett/sncloud](https://github.com/rnbennett/sncloud) |
| `obsidian-headless` | Official Obsidian CLI for headless vault sync — used by the `obsidian-sync` service | [github.com/obsidianmd/obsidian-headless](https://github.com/obsidianmd/obsidian-headless) |
| `gosu` | Lightweight privilege-dropping tool used in container entrypoints to run processes as the configured `PUID`/`PGID` | [github.com/tianon/gosu](https://github.com/tianon/gosu) |
| `uv` | Fast Python package manager and project tool (recommended for native installs) | [docs.astral.sh/uv](https://docs.astral.sh/uv/) |

---

## License

Apache-2.0
