# sn2md-batches

`sn2md-batches.sh` is a zsh wrapper that runs multiple [sn2md](https://github.com/sn2md/sn2md) jobs from a single YAML file. Each job can target a different Supernote input directory, output location, and TOML configuration while the script handles concurrency, logging, and per-job environment loading.

## Requirements
- zsh (script shebang)
- [`yq`](https://mikefarah.gitbook.io/yq/) (Mike Farah) for YAML parsing
- [`uv`](https://astral.sh/uv) if you want the runner to install sn2md automatically (otherwise provide `sn2md` yourself)
- Access to the Supernote input directories referenced by your jobs

Install `yq` with Homebrew:

```bash
brew install yq
```

## Managed sn2md Environment (uv)
The runner can bootstrap a project-local virtual environment at `.venv/` using [`uv`](https://astral.sh/uv). Use the `--setup` flag to perform this once (or whenever you want to update the tooling):

1. Install uv if you have not already:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Run the setup step (the flag must be used by itself):

   ```bash
   ./sn2md-batches.sh --setup
   ```

   Setup will:
   - create `.venv/` with Python 3.11 via `uv venv --python 3.11 .venv`
   - install `sn2md` from PyPI using `uv pip install --python .venv/bin/python sn2md`
   - install the Ollama llm plugin (`llm-ollama`) so you can register local vision models

After setup, the `sn2md` binary in `.venv/bin/sn2md` is used automatically. To point at a different executable, set `SN2MD_EXEC=/absolute/path/to/sn2md` before running the script. You can also export `UV_PYTHON_VERSION` or `UV_BIN` if you need to control the interpreter version or uv location.

## Quick Start
1. Clone or copy this repo into a workspace with your Supernote exports.
2. Adjust `jobs.yaml` (or create your own) to point at real input/output paths and TOML configs. See [AGENTS.md](AGENTS.md) for the full schema.
3. Run setup once (installs sn2md into `.venv/`; the flag must be used alone):

   ```bash
   ./sn2md-batches.sh --setup
   ```

4. Apply the local sn2md patches so the CLI supports per-note metadata and `attachments/` media folders:

   ```bash
   zsh patch.sh
   ```

5. Preview the run without touching the filesystem:

   ```bash
   ./sn2md-batches.sh --dry-run --config jobs.yaml
   ```

   Dry run prints the exact `sn2md` command per job and lists any note/image files discovered under each input directory.

6. Execute the conversions (serial by default). Remove `--dry-run` once satisfied:

   ```bash
   ./sn2md-batches.sh --config jobs.yaml
   ```

   Add `--jobs N` to enable parallel processing (caps at 8), and `--no-color` if piping output.

## Configuration Tips
- `defaults` in the YAML file provide shared values for `input`, `output`, `env_file`, and common flags.
- Jobs that specify a TOML `config` only receive `-o` and `-c`; move per-job tuning into the TOML file.
- Jobs without a config inherit any `flags.*` or `extra_args` defined in YAML (plus CLI arguments that follow the script-level switches).
- Per-job `env_file` values let you inject different credential sets before each `sn2md` invocation.
- The patched `sn2md` writes note assets under `note/output/attachments/` and per-note metadata under `note/output/.meta/` so multiple notes can share a dated folder without conflicts. Reference images using the relative `attachments/...` links that the generator emits.

## Sample Fixtures
The repository includes:
- `jobs.example.yaml` – workspace-relative example defaults.
- `tests/jobs.test.yaml` and `tests/test.toml` – minimal fixtures for local validation.
- `in/` and `out/` directories ignored by git so you can stage local inputs/outputs safely.

## Troubleshooting
- Missing `yq` or `sn2md` will stop the script early with a clear error message. Use `--setup` to install sn2md locally or install your own before running jobs.
- Network errors (e.g., OpenAI connectivity) surface in the job log; rerun the job after connectivity is restored.
- Use `--dry-run` to verify paths and configs before hitting the network or writing files.
- If `sn2md` is reinstalled, rerun `zsh patch.sh` so the `attachments/` and `.meta/` behaviour is restored before exporting notes.
