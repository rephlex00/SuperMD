# CLI Commands

SuperMD is invoked as `supermd [GLOBAL OPTIONS] COMMAND [ARGS]`.

---

## Global Options

These options apply to the `file` and `directory` commands. The `run`, `watch`, `gui`, `meta`, `config`, and `service` commands manage their own options independently.

| Option | Default | Description |
|---|---|---|
| `-c, --config PATH` | `config/supermd.yaml` | Path to a supermd YAML config file |
| `-o, --output PATH` | `supernote` | Output directory |
| `-f, --force` | off | Reprocess files even if input hash is unchanged or output has been hand-edited |
| `--progress / --no-progress` | on | Show a tqdm progress bar |
| `-l, --level TEXT` | `WARNING` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `-m, --model TEXT` | *(from config)* | Override the LLM model |
| `-v, --version` | — | Print the version and exit |

---

## file

Convert a single file to Markdown.

```bash
supermd file <PATH> [GLOBAL OPTIONS]
```

Supported formats: `.note`, `.spd`, `.pdf`, `.png`.

**Examples**

```bash
supermd file notes/20260313_143000.note -o ./output
supermd file scan.pdf -o ./output --model gpt-4o
supermd file page.png -o ./output --no-progress
```

If the input hash matches the stored hash the file is silently skipped. Use `-f` to force reprocessing.
If the output file has been hand-edited since last transcription, SuperMD refuses to overwrite it and prints a warning. Use `-f` to override.
If a file contains `ignoresnlock: true` in its YAML frontmatter it is always skipped, even with `-f`.

---

## directory

Convert all supported files in a directory.

```bash
supermd directory <PATH> [GLOBAL OPTIONS]
```

Unsupported file types are silently ignored. Skip/protect behaviour is identical to `file`.

**Example**

```bash
supermd directory ~/Supernote/Note/Personal -o ~/Vault/Personal --force
```

---

## run

Run all batch jobs defined in a config file.

```bash
supermd run [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--config PATH` | `config/supermd.yaml` | Config file to load jobs from |
| `-j, --jobs N` | `1` | Number of jobs to run in parallel |
| `--dry-run` | off | Print what would be processed without converting |
| `--debug` | off | Enable verbose debug logging |

Jobs are defined in the `jobs` section of the config. Each job specifies an `input` directory, an `output` directory, and optional per-job overrides. See [configuration.md](configuration.md) for details.

**Example**

```bash
supermd run --config config/supermd.yaml --jobs 2
supermd run --dry-run  # preview without converting
```

---

## watch

Watch all job input directories for changes and auto-convert modified files.

```bash
supermd watch [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--config PATH` | `config/supermd.yaml` | Config file to load jobs from |
| `-j, --jobs N` | `1` | Number of jobs to run in parallel |
| `-d, --delay SECONDS` | `30.0` | Seconds to wait after the last change event before processing (debounce). Also readable from `SUPERMD_WATCH_DELAY` env var. |

SuperMD uses watchdog to monitor the filesystem. The debounce delay prevents rapid repeated conversions when a sync client writes files incrementally.

**Example**

```bash
supermd watch --config config/supermd.yaml --delay 10
```

---

## meta

Manage the SQLite metadata database that tracks file hashes and skip/protect state.

The metadata database lives at `{output}/.meta/metadata`.

### meta list

```bash
supermd meta list [--config PATH] [--verbose]
```

Print a table of tracked files, their state (current / changed / missing), and stored hashes.
`--verbose` adds raw hash columns to the output.

### meta rebuild

```bash
supermd meta rebuild [--config PATH] [--dry-run]
```

Scan each job's input and output directories and re-populate the metadata database from the files on disk. Useful after manually copying or renaming notes.

### meta rm

```bash
supermd meta rm [--config PATH] [--dry-run]
```

Delete all metadata for every job in the config, resetting the tracking database. The next `run` or `watch` will re-process all files from scratch.

---

## config keys

Manage LLM API keys stored in the `llm` keystore.

### config keys set

```bash
supermd config keys set <NAME> [--value KEY]
```

Store an API key in the `llm` keystore. `NAME` is the provider identifier (e.g. `openai`, `gemini`). The key value is prompted interactively if `--value` is omitted.

```bash
supermd config keys set openai
supermd config keys set gemini --value "AIza..."
```

> In Docker or CI, prefer setting the corresponding environment variable (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`) instead of using the keystore.

### config keys list

```bash
supermd config keys list
```

Show all keys in the `llm` keystore and any recognised API key environment variables, with values masked to the last 4 characters.

### config keys path

```bash
supermd config keys path
```

Print the filesystem path to the `llm` keys JSON file.

---

## gui

Launch a web-based configuration editor for `supermd.yaml`.

```bash
supermd gui [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `-c, --config PATH` | `config/supermd.yaml` | Config file to edit |
| `-p, --port N` | `8734` | Port for the HTTP server |
| `-H, --host ADDR` | `127.0.0.1` | Bind address. Use `0.0.0.0` for remote access (e.g. Docker, Tailscale) |
| `-t, --token TEXT` | *(auto)* | Bearer token for API auth. Also readable from `SUPERMD_GUI_TOKEN` env var. Auto-generated when host is not localhost |

The GUI serves a single-page app at `http://<host>:<port>` with a form for editing all config fields (model, prompts, templates, defaults, jobs). Changes are validated through Pydantic and written back to the YAML file with comments preserved.

**Authentication:** When binding to a non-localhost address, a random bearer token is generated and printed to stdout. All `/api/*` requests require an `Authorization: Bearer <token>` header. The token is embedded in the served HTML page so the browser client authenticates automatically. When running on localhost, no auth is required.

**Examples**

```bash
# Local editing (opens browser automatically)
supermd gui

# Remote access (e.g. from Docker or over Tailscale)
supermd gui --host 0.0.0.0 --port 8734
# Token is printed to stdout — use it to access from another device

# Explicit token
supermd gui --host 0.0.0.0 --token my-secret
```

---

## service

Manage SuperMD as a macOS launchd background service. The service runs `supermd watch` continuously.

### service install

```bash
supermd service install [--config PATH] [--dry-run]
```

Generate a launchd plist and load it into `~/Library/LaunchAgents`. Use `--dry-run` to preview the plist without installing.

### service uninstall

```bash
supermd service uninstall
```

Unload and remove the launchd plist.

### service start / stop

```bash
supermd service start
supermd service stop
```

Start or stop the loaded service without removing the plist.

### service status

```bash
supermd service status
```

Print the current state of the launchd service (running / stopped / not installed).

### service logs

```bash
supermd service logs [--lines N] [--follow]
```

| Option | Default | Description |
|---|---|---|
| `-n, --lines N` | `10` | Number of recent log lines to show |
| `-f, --follow` | off | Stream new log output (like `tail -f`) |
