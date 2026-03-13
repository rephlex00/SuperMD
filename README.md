# SuperMD

Convert [Supernote](https://supernote.com/) `.note` files (and PDFs, PNGs, and Atelier `.spd` files) into Markdown using an LLM. Designed for syncing handwritten notes into an [Obsidian](https://obsidian.md/) vault.

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
| Python ≥ 3.11 | Required |
| [uv](https://docs.astral.sh/uv/) | Recommended |
| LLM API key | Required |

> **Note:** Any model supported by the [llm](https://llm.datasette.io/en/stable/plugins/index.html) ecosystem works. The default is `gpt-4o-mini` (requires an OpenAI API key).

---

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/your-org/supermd.git
cd supermd

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
| `output_path_template` | Directory structure template (e.g. `{{ format_date('YYYY/MM MMM') }}`) |
| `output_filename_template` | Output filename template (e.g. `{{file_basename}}.md`) |
| `jobs` | List of input/output folder pairs for batch processing |

### 3. Set your API key

```bash
export OPENAI_API_KEY="sk-..."
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
  -c, --config PATH       Path to supermd.yaml config
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

## License

Apache-2.0
