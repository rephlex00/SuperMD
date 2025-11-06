# sn2md Agents

## Runner Overview
- `sn2md-batches.sh` orchestrates multiple `sn2md directory …` runs with isolated logging so job output never interleaves. Use `--setup` (alone) to bootstrap the local `.venv/` with sn2md and `llm-ollama`, then `zsh patch.sh` to apply the local sn2md patches.
- By default it reads `jobs.yaml` from the script directory; override with `--config path/to/jobs.yaml`.
- Supports `--jobs N` (serial by default), `--dry-run` for a safe preview, and `--no-color`. CLI args that follow those switches flow through only when a job lacks a TOML config.
- Requires `yq` (Mike Farah) for YAML parsing and `sn2md` (install locally with `--setup` or provide your own).
- Each job logs a concise summary and the script exits non-zero if any job fails.

## Execution Flow
- Loads shared defaults from YAML once, then captures each job definition as JSON for processing.
- Determines concurrency from `--jobs`, defaulting to single-threaded execution; uses a bounded worker pool to keep logs per job.
- Normalises paths (tilde expansion, trimming), validates that required inputs/configs exist, and prepares the output directory (skipped during dry runs). Patched sn2md runs emit note assets into `.image/` and per-note metadata into `.meta/` within each note’s destination folder.
- Buffers stdout/stderr for each job, then prints the block when the job completes.
- Sources `defaults.env_file` or a per-job `env_file` just before invoking `sn2md`, letting each job use different credentials.
- If a job specifies a TOML `config`, the runner calls `sn2md` with only `-o`/`-c`, so the config governs all other options. Jobs without a config inherit YAML defaults for flags and extra args (plus any pass-through CLI parameters).
- `--dry-run` renders the would-be command, lists note/image files under the input directory, and skips directory creation and the `sn2md` call.

## Configuration (`jobs.yaml`)
- **defaults**  
  - `input`: fallback Supernote source path whenever a job omits `input`.
  - `output`: fallback destination root (`~/Vault` in the base example).
  - `env_file`: optional credentials file sourced for each job.
  - `flags`: default `sn2md` options (`force`, `progress`, `level`, `model`).
  - `extra_args`: additional CLI arguments appended only for jobs without a TOML config.
- **jobs[]**  
  - Required fields: `name`, `output`, plus either an explicit `input` or a reliance on `defaults.input`.
  - Optional overrides: `config`, `env_file`, `flags.*`, `extra_args[]`.
  - Jobs with a `config` delegate behaviour to that TOML; ignore YAML flag overrides and put tuning in the config file instead.

## Defined Agents (sample `jobs.yaml`)
- **Journal** → `/Volumes/Supernote/Journal` → `~/Vault/Journal` using `~/sn2md-configs/journal.toml`.
- **Work** → `/Volumes/Supernote/Work` → `~/Vault/Work` using `~/sn2md-configs/work.toml`.
- **Sketchbook** → `/Volumes/Supernote/Sketchbook` → `~/Vault/Sketchbook` using `~/sn2md-configs/sketch.toml`, sourcing `~/.env-sketch`.

## Adding Agents
- Copy an existing job entry, update `name`, `output`, and either supply `input` or rely on `defaults.input`; point `config` at the correct TOML.
- Keep YAML `flags.*`/`extra_args` for jobs without configs; otherwise move tuning into the TOML.
- Provide per-job `env_file` values for distinct credential sets.
- Use `--config` to swap to alternate YAML suites (e.g., personal vs. work collections).
