# sn2md Agents

## Runner Overview
- `sn2md-batches.sh` wraps `sn2md directory …` so multiple Supernote → Markdown jobs run together without interleaved output.
- Uses `jobs.yaml` by default; override with `--config path/to/jobs.yaml`.
- Accepts `--jobs N` (defaults to `1` for serial execution) and `--no-color`; CLI args after those pass through only for jobs that run without a TOML config.
- Requires `yq` (Mike Farah) to parse YAML and `sn2md` to execute conversions.
- Buffers each job’s log, prints a color-coded summary block, and exits non-zero when any job fails.

## Execution Flow
- Reads YAML defaults once (including optional `defaults.input`), then loads every job definition into a queue.
- Decides concurrency from `--jobs` (defaults to single-threaded), throttling background workers to avoid interleaving output.
- Before invoking `sn2md`, the runner expands `~`, trims whitespace, validates that `input` exists, `config` (if provided) is readable, and ensures the `output` directory exists.
- Collects job output/log in a temp file; prints it after the job finishes and removes the temp file.
- Sources an env file (`defaults.env_file` or per-job override) when present so credentials can differ per job.
- When a job supplies a TOML `config`, the runner invokes `sn2md` with only `-o` and `-c`, letting the config control every other option and ignoring pass-through CLI arguments. Jobs without a config fall back to YAML defaults for flags and merged extra args (plus any pass-through CLI parameters).

## Configuration Schema (`jobs.yaml`)
- **defaults**  
  - `input`: fallback source directory if a job omits `input`.
  - `output`: fallback destination (`~/Vault`).
  - `env_file`: optional file (e.g., `~/.env`) sourced before each job.
  - `flags`: maps directly to `sn2md` options (`force`, `progress`, `level`, `model` default `gpt-4o-mini`).
  - `extra_args`: list appended to jobs that run without a TOML config.
- **jobs[]** (each entry is an agent)  
  - Required: `name`, `output`, plus either `input` or rely on `defaults.input`. Provide `config` when you want the TOML to own behavior.  
  - Optional overrides: `config`, `env_file`, `flags.*`, `extra_args[]`. Missing values inherit from `defaults`.
  - When `config` is present, `flags.*` and `extra_args[]` are ignored, so move that tuning into the TOML file instead. Without `config`, the runner uses defaults plus per-job overrides (plus pass-through CLI args) to build the CLI.

## Defined Agents
- **Journal**  
  - Input `/Volumes/Supernote/Journal`, output `~/Vault/Journal`, config `~/sn2md-configs/journal.toml`.  
  - Delegates processing options to the TOML; only input/output are sent via CLI.
- **Work**  
  - Input `/Volumes/Supernote/Work`, output `~/Vault/Work`, config `~/sn2md-configs/work.toml`.  
  - Inherits the shared defaults for flags/env and lets the TOML drive behavior.
- **Sketchbook**  
  - Input `/Volumes/Supernote/Sketchbook`, output `~/Vault/Sketchbook`, config `~/sn2md-configs/sketch.toml`.  
  - Sources `~/.env-sketch`, otherwise defers to the TOML for model/flag choices.

## Adding or Adjusting Agents
- Duplicate an existing job block in `jobs.yaml` and adjust `name`, `output`, and either `input` or ensure `defaults.input` points to the right source, plus `config`.
- With a TOML `config`, move flag choices into the file; the runner will not pass YAML defaults.
- Provide per-job `extra_args` only for jobs without a config (they append after global args).
- Use `--config` to point the runner at alternate YAML files (e.g., team-specific suites).
- Combine with `personal.toml` or other `sn2md` configs referenced by each job’s `config` field.
