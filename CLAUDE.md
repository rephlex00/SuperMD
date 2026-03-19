# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SuperMD converts Supernote handwritten notes (`.note`, `.spd`, PDF, PNG) into Markdown via LLM transcription. It integrates with Obsidian vaults and supports batch processing, file watching, a macOS launchd service, and Docker deployment (standalone container or full 3-service stack).

## Commands

```bash
# Install dependencies (uv preferred)
uv sync
uv sync --extra test   # include test deps

# LLM setup (one-time, per provider)
llm install llm-gemini         # for Gemini models
llm install llm-claude-3       # for Claude models
llm keys set openai            # or set OPENAI_API_KEY env var
supermd config keys set <key>  # alternative: set via supermd CLI

# Run tests
pytest
pytest tests/test_core.py -v         # single file
pytest tests/test_core.py::test_name # single test

# Run CLI
supermd file path/to/note.note -o ./output
supermd directory path/to/notes/ -o ./output
supermd run --config config/supermd.yaml
supermd watch --config config/supermd.yaml
supermd meta list
supermd meta rebuild
```

## Architecture

The pipeline flows: CLI → Batches/Watcher → Converter → [Extractor + AI + Context + Metadata] → Markdown output.

**`converter.py`** — Core engine. Orchestrates extraction, LLM calls per page, Jinja2 template rendering, and metadata updates. Skip logic: if input hash is unchanged OR if output has been hand-edited (detected via metadata hash), conversion is skipped. The `ignoresnlock: true` YAML frontmatter flag in an output file permanently protects it from overwriting.

**`importers/`** — Format-specific image extractors. Each importer extends the `ImageExtractor` ABC from `types.py` (package root) with `extract_images()` and `get_notebook()`. The `get_extractor()` factory in `importers/__init__.py` maps file extensions to extractors. Formats: `.note` (supernotelib), `.spd` (atelier), PDF (PyMuPDF), PNG (passthrough).

**`supernotelib/`** — Vendored Supernote parsing library. Do not modify without understanding the upstream format.

**`metadata_db.py`** — SQLite DB tracking SHA-1 hashes of input and output files. Drives skip/protect logic. Located at `{output}/.meta/metadata`.

**`batches.py`** — Runs multiple job configs in parallel via `ThreadPoolExecutor`. Uses the unified `SuperMDConfig`.

**`watcher.py`** — watchdog-based filesystem watcher. Debounces events (default 30s) before triggering conversion.

**`context.py`** — Builds the Jinja2 template context from notebook metadata (links, keywords, title) and adds date helpers (`dailynote` for Obsidian date format).

**`config.py`** — Unified configuration model (`SuperMDConfig`) loaded from a single YAML file. Contains AI settings, prompts, templates, processing defaults, and job definitions. Replaces the former split between `settings.toml` and `jobs.yaml`.

**`service.py`** — macOS launchd plist management for running SuperMD as a background service.

**`console.py`** — Custom logging handler that integrates stdlib logging with styled console output and redirects `tqdm.write` to stdout.

**`cli.py`** — Click-based CLI entry point. Defines all subcommands (`file`, `directory`, `run`, `watch`, `meta`, `config`).

**`ai_utils.py`** — LLM interaction helpers. Wraps the `llm` library for page transcription and title generation calls.

## Docker

**Standalone** (`docker-compose.yml` at project root) — single SuperMD container in watch mode. API key passed via `.env`. Input/output via bind mounts.

**Full stack** (`docker/stack/`) — 3-service pipeline:
- `supernote-sync` — polls Supernote Cloud (optional, `--profile cloud`)
- `supermd` — converts notes in watch mode
- `obsidian-sync` — syncs vault via obsidian-headless CLI

Key files:
- `Dockerfile` — multi-stage build (builder installs uv + llm plugins; runtime uses Python 3.12-slim + gosu for UID remapping)
- `entrypoint.sh` — drops privileges to `PUID`/`PGID` before running supermd
- `docker/stack/docker-compose.yml` — full stack compose with secrets
- `docker/stack/supermd-entrypoint.sh` — maps `LLM_PROVIDER` + secret file to the correct env var
- `docker/stack/init-secrets.sh` — creates placeholder secret files
- `docker/stack/setup.sh` — interactive setup wizard (creates secrets, .env, tests credentials)
- `docker/stack/supernote-sync/sync.py` — Supernote Cloud sync with OTP verification and token-based auth

Secrets in the stack are stored as files in `docker/stack/secrets/` (not env vars). The `supermd-entrypoint.sh` reads `/run/secrets/llm_api_key` and exports `OPENAI_API_KEY`/`GEMINI_API_KEY`/`ANTHROPIC_API_KEY` based on `LLM_PROVIDER`.

```bash
# Standalone
docker compose up -d
docker compose logs -f

# Full stack
cd docker/stack
docker compose run --rm setup      # interactive first-time config
docker compose --profile cloud up -d
```

## Docker Stack Gotchas

- **sncloud fork**: `supernote-sync` uses `rnbennett/sncloud@main` (not PyPI) for CSRF token and OTP/E1760 verification support. The Supernote Cloud API requires `X-XSRF-TOKEN` on all POST requests (as of March 2026).
- **Supernote Cloud E1760 flow**: New device login raises `AuthenticationError("__E1760__:<timestamp>")` → `send_verification_code()` → `verify_otp()` → sometimes needs a follow-up `login()` to get the JWT token.
- **Token persistence**: `setup.sh` saves the JWT access token to `secrets/supernote_token`; `sync.py` checks for it before attempting login. Tokens expire ~30 days.
- **Shell scripts must target Bash 3.2** (macOS default): no `${var,,}` lowercase — use `printf '%s' "$1" | tr '[:upper:]' '[:lower:]'` instead.
- **Never string-interpolate credentials into inline Python/shell**: passwords with `'`, `"`, `$`, etc. will break. Pass via environment variables and read with `os.environ`.
- **All secret placeholder files must exist** before `docker compose up` — Compose fails with "bind source path does not exist" otherwise. `setup.sh` creates them upfront.

## Configuration

**`config/supermd.yaml`** — Unified config (not committed; use `supermd.example.yaml` as template). Contains `model`, `prompt`, `template`, `output_path_template`, `output_filename_template`, processing `defaults`, and `jobs` list with per-job `input`/`output` paths and optional overrides.

**`.env.example`** — Template for Docker environment variables (standalone container). Copy to `.env` and fill in.

**Environment:** API keys are managed by the `llm` library — run `llm keys set <provider>` (e.g., `llm keys set openai`, `llm keys set gemini`) or set the provider's env var (e.g., `OPENAI_API_KEY`, `GEMINI_API_KEY`). Models require the matching `llm` plugin installed first (see Commands above). SuperMD will print a `supermd config keys set` hint if a key is missing at runtime.

## Key Patterns

- **Title derivation**: If `note_title_prompt` is set in config, a second LLM call generates a short title after transcription; result is available as `{{title}}` in templates.
- **DATE tokens**: Output path and filename templates support `{{DATE:<format>}}` tokens (e.g., `{{DATE:YYYY/MM MMM}}`). `date_utils.py` handles expansion; format tokens follow Obsidian conventions (YYYY, MM, MMM, DD, dddd, etc.).
- **DATE token preprocessing**: Any code path constructing a Jinja2 `Template` from `config.output_path_template` or `config.output_filename_template` **must** call `expand_date_tokens(s, ctime)` first — Jinja2 will raise `TemplateSyntaxError` on the `:` in `{{DATE:...}}`. Follow the `preprocess()` helper pattern in `converter.py`.
- **Skip protection**: `converter.py` raises a custom exception to skip files; callers catch it to log and continue.
- **Cooldown**: A configurable delay between page LLM calls prevents rate limiting.
- **Output path templating**: Both directory and filename are Jinja2 templates evaluated with the context dict (year, month, file_basename, dailynote, etc.).
- **Tests**: `tests/conftest.py` provides fixtures including temp dirs and mock configs. Tests use `SuperMDConfig` from `supermd.config`.
