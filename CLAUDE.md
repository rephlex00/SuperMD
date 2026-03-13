# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`sn2md` converts Supernote handwritten notes (`.note`, `.spd`, PDF, PNG) into Markdown via LLM transcription. It integrates with Obsidian vaults and supports batch processing, file watching, and a macOS launchd service.

## Commands

```bash
# Install dependencies (uv preferred)
uv sync
uv sync --extra test   # include test deps

# Run tests
pytest
pytest tests/test_core.py -v         # single file
pytest tests/test_core.py::test_name # single test

# Run CLI
sn2md-cli file path/to/note.note -o ./output
sn2md-cli directory path/to/notes/ -o ./output
sn2md-cli run --config config/jobs.local.yaml
sn2md-cli watch --config config/jobs.local.yaml
sn2md-cli meta list
sn2md-cli meta rebuild
```

## Architecture

The pipeline flows: CLI → Batches/Watcher → Converter → [Extractor + AI + Context + Metadata] → Markdown output.

**`converter.py`** — Core engine. Orchestrates extraction, LLM calls per page, Jinja2 template rendering, and metadata updates. Skip logic: if input hash is unchanged OR if output has been hand-edited (detected via metadata hash), conversion is skipped. The `ignoresnlock: true` YAML frontmatter flag in an output file permanently protects it from overwriting.

**`importers/`** — Format-specific image extractors. Each importer implements a common ABC (`types.py`) with `extract_images()` and `get_notebook()`. Formats: `.note` (supernotelib), `.spd` (atelier), PDF (PyMuPDF), PNG (passthrough).

**`supernotelib/`** — Vendored Supernote parsing library. Do not modify without understanding the upstream format.

**`metadata_db.py`** — SQLite DB tracking SHA-1 hashes of input and output files. Drives skip/protect logic. Located at the output root as `.sn2md_metadata.db`.

**`batches.py`** — Runs multiple job configs in parallel via `ThreadPoolExecutor`. Reads from YAML job files.

**`watcher.py`** — watchdog-based filesystem watcher. Debounces events (default 30s) before triggering conversion.

**`context.py`** — Builds the Jinja2 template context from notebook metadata (links, keywords, title) and adds date helpers (`dailynote` for Obsidian date format).

**`service.py`** — macOS launchd plist management for running sn2md as a background service.

**`console.py`** — Custom logging handler that integrates stdlib logging with styled console output and redirects `tqdm.write` to stdout.

## Configuration

**`config/settings.toml`** — Primary config with `model`, `prompt`, `template` (Jinja2), `output_path_template`, `output_filename_template`, and flags like `ignoretasks` and `handwritten`.

**`config/jobs.local.yaml`** — Batch job definitions (not committed; use `jobs.example.yaml` as template). Specifies `defaults` and per-job `input`/`output` paths.

**Environment:** `OPENAI_API_KEY` (or equivalent for the configured LLM provider). The `llm` library is used as the LLM abstraction layer — models are specified in `settings.toml` using the `llm` plugin naming convention (e.g., `gemini/gemini-2.5-flash`, `gpt-4o-mini`).

## Key Patterns

- **Skip protection**: `converter.py` raises a custom exception to skip files; callers catch it to log and continue.
- **Cooldown**: A configurable delay between page LLM calls prevents rate limiting.
- **Output path templating**: Both directory and filename are Jinja2 templates evaluated with the context dict (year, month, file_basename, dailynote, etc.).
- **Tests**: `tests/conftest.py` provides fixtures including temp dirs and mock notebooks. Tests use real fixture files from `tests/fixtures/`.
