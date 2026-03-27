# Configuration

SuperMD is configured through a single YAML file, typically `config/supermd.yaml`. Copy `config/supermd.example.yaml` as your starting point.

```bash
cp config/supermd.example.yaml config/supermd.yaml
```

The config is passed to most commands via `--config`:

```bash
supermd run --config config/supermd.yaml
supermd watch --config config/supermd.yaml
```

For `supermd file` and `supermd directory`, the config is read from the global `-c` option (default: `config/supermd.yaml`).

---

## Top-level fields

### `model`

The LLM model used to transcribe each page.

```yaml
model: gpt-4o-mini
```

Uses the `llm` plugin naming convention. The default is `gpt-4o-mini`. Install the matching plugin before using a non-OpenAI model:

```bash
llm install llm-gemini    # Google Gemini
llm install llm-claude-3  # Anthropic Claude
```

Common values:

| Value | Provider | Plugin required |
|---|---|---|
| `gpt-4o-mini` | OpenAI | *(built-in)* |
| `gpt-4o` | OpenAI | *(built-in)* |
| `gemini/gemini-2.5-flash` | Google | `llm-gemini` |
| `claude-sonnet-4-6` | Anthropic | `llm-claude-3` |

Can be overridden per-job in the `jobs` list, and overridden at runtime with `supermd -m <model>`.

---

### `prompt`

The system prompt sent to the LLM for each page image. The `{context}` placeholder is replaced with the Markdown output from the previous page, giving the model continuity across multi-page notes.

```yaml
prompt: |
  <context>
  {context}
  </context>
  Convert the image to markdown.
```

The prompt is sent once per page. For a multi-page note, each call receives the output of the previous page as context.

---

### `note_title_prompt`

*Optional.* If set, SuperMD makes a second LLM call after all pages are transcribed to generate a short human-readable title. The `{markdown}` placeholder is replaced with the fully assembled transcription.

```yaml
note_title_prompt: |
  Generate a concise title of 4 to 7 words for the following note.
  Output only the title, nothing else.

  Note:
  {markdown}

  Title:
```

The result is available as `{{title}}` in `template`, `output_path_template`, and `output_filename_template`. If `note_title_prompt` is omitted or commented out, `{{title}}` is an empty string.

---

### `output_path_template`

A Jinja2 template that determines the subdirectory (relative to a job's `output`) where the converted file is written.

```yaml
output_path_template: "{{DATE:YYYY/MM MMM}}"
```

Supports all [template variables](templates.md) and [DATE tokens](templates.md#date-tokens). Default: `{{file_basename}}`.

---

### `output_filename_template`

A Jinja2 template for the output filename.

```yaml
output_filename_template: "{{file_basename}}.md"
```

Supports all [template variables](templates.md) and [DATE tokens](templates.md#date-tokens). Default: `{{file_basename}}.md`.

---

### `template`

A Jinja2 template rendered once per input file to produce the final `.md` output. Supports all [template variables](templates.md) and [DATE tokens](templates.md#date-tokens).

```yaml
template: |
  ---
  date: {{DATE:YYYY-MM-DD[T]HHmmss}}
  title: "{{title}}"
  tags: handwritten
  ---
  {{llm_output}}

  ## Images
  {% for image in images %}
  ![{{ image.name }}]({{image.name}})
  {%- endfor %}
```

The `ignoresnlock` frontmatter field controls overwrite protection:

| Value | Behaviour |
|---|---|
| `false` *(default)* | File can be re-transcribed if the source changes |
| `true` | File is permanently protected; SuperMD will never overwrite it, even with `--force` |

---

### `defaults`

Processing defaults that apply to all jobs unless overridden at the job level.

```yaml
defaults:
  force: false
  progress: true
  level: INFO
  cooldown: 5.0
```

| Field | Type | Default | Description |
|---|---|---|---|
| `force` | bool | `false` | Re-process files even if the input hash is unchanged or the output has been hand-edited |
| `progress` | bool | `true` | Show a tqdm progress bar. Automatically disabled when `jobs > 1` in `supermd run` |
| `level` | string | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `cooldown` | float | `5.0` | Seconds to wait between LLM calls for successive pages within a single file. Helps avoid rate-limit errors. Set to `0` to disable |

---

### `jobs`

A list of input/output directory pairs. Used by `supermd run` and `supermd watch`.

```yaml
jobs:
  - name: Personal
    input: ~/Supernote/Note/Personal
    output: ~/Vault/Personal/Supernote

  - name: Work
    input: ~/Supernote/Note/Work
    output: ~/Vault/Work/Supernote
    model: gemini/gemini-2.5-flash
    cooldown: 2.0
```

#### Required fields per job

| Field | Description |
|---|---|
| `name` | Human-readable label shown in logs |
| `input` | Source directory. Supports `~` and `$ENV_VAR` expansion |
| `output` | Destination directory. Supports `~` and `$ENV_VAR` expansion |

#### Optional per-job overrides

Any of the following fields override the corresponding value in `defaults` for that job only:

| Field | Description |
|---|---|
| `model` | Override the LLM model |
| `force` | Override force-reprocess |
| `progress` | Override progress bar display |
| `level` | Override logging level |
| `cooldown` | Override page cooldown |

---

## Skip and lock behaviour

SuperMD tracks SHA-1 hashes of input and output files in a SQLite database at `{output}/.meta/metadata`.

| Condition | Behaviour | Override |
|---|---|---|
| Input hash matches stored hash | File is skipped (no change detected) | `force: true` or `-f` |
| Output hash differs from stored hash | File is skipped (output was hand-edited) | `force: true` or `-f` |
| Output frontmatter has `ignoresnlock: true` | File is **always** skipped | None — permanent protection |

---

## Environment variables

API keys can be supplied as environment variables instead of using the `llm` keystore:

| Variable | Provider |
|---|---|
| `OPENAI_API_KEY` | OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |

`SUPERMD_WATCH_DELAY` sets the default debounce delay for `supermd watch` (seconds, float).

Environment variables take precedence over the `llm` keystore for API keys.

### GUI variables

| Variable | Default | Description |
|---|---|---|
| `SUPERMD_GUI_TOKEN` | *(auto-generated)* | Bearer token for GUI API authentication. If unset and the GUI binds to a non-localhost address, a random token is generated and printed to stdout |
| `SUPERMD_GUI_PORT` | `8734` | Host port mapping for the Docker GUI service |

---

## Web GUI

SuperMD includes a browser-based configuration editor. See [commands.md — gui](commands.md#gui) for CLI usage.

```bash
# Local
supermd gui

# Remote (Docker / Tailscale)
supermd gui --host 0.0.0.0
```

The GUI reads and writes the same `supermd.yaml` file. YAML comments are preserved on save. All changes are validated through Pydantic before writing.
