# Templates and Variables

SuperMD uses [Jinja2](https://jinja.palletsprojects.com/) for all template fields in the config. Three config fields accept templates:

| Field | What it controls |
|---|---|
| `template` | The full content of the output `.md` file |
| `output_path_template` | The subdirectory (relative to `output`) where the file is written |
| `output_filename_template` | The filename of the output `.md` file |

---

## Template variables

All three template fields share the same variable set.

### File variables

Available for every supported file format.

| Variable | Type | Example | Description |
|---|---|---|---|
| `file_basename` | string | `20260313_143000` | Input filename without extension |
| `file_name` | string | `/path/to/file.note` | Full absolute path to the input file |
| `ctime` | `datetime` | — | Date parsed from the filename (`YYYYMMDD_HHMMSS` or `YYYYMMDD`). Falls back to filesystem mtime if the filename does not match |
| `mtime` | `datetime` | — | Filesystem modification time |
| `title` | string | `My Note Title` | LLM-derived title. Empty string if `note_title_prompt` is not set in config |

### Transcription variables

Available in `template` only (not in path/filename templates, since transcription hasn't run yet at path-resolution time).

| Variable | Type | Description |
|---|---|---|
| `llm_output` | string | Full transcribed Markdown from all pages joined together |
| `markdown` | string | Alias for `llm_output` |
| `images` | list | Extracted page images (see below) |

Each item in `images` has:

| Attribute | Example | Description |
|---|---|---|
| `.name` | `page_001.png` | Filename of the extracted page image |
| `.rel_path` | `attachments/page_001.png` | Path relative to the output directory |
| `.link` | `attachments/page_001.png` | Same as `rel_path` — use in Markdown image links |
| `.abs_path` | `/Users/.../attachments/page_001.png` | Absolute path on disk |

### Notebook variables

Populated for `.note` files only. Empty lists for all other formats.

| Variable | Type | Description |
|---|---|---|
| `links` | list | Cross-references stored in the notebook |
| `keywords` | list | Keywords/tags stored in the notebook |
| `titles` | list | Title annotations stored in the notebook (transcribed via a separate LLM call using `title_prompt`) |

Each item in `links`:

| Attribute | Values | Description |
|---|---|---|
| `.page_number` | integer | Page the link appears on |
| `.type` | `"page"`, `"file"`, `"web"` | Link target type |
| `.name` | string | Link target name or filename |
| `.inout` | `"in"`, `"out"` | Whether the link is incoming or outgoing |

Each item in `keywords`:

| Attribute | Description |
|---|---|
| `.page_number` | Page the keyword appears on |
| `.content` | Keyword text |

Each item in `titles`:

| Attribute | Description |
|---|---|
| `.page_number` | Page the title appears on |
| `.content` | Title text (transcribed by LLM) |
| `.level` | Heading level (integer) |

---

## DATE tokens

Any of the three template fields can include `{{DATE:format}}` tokens. SuperMD expands these before passing the string to Jinja2 (Jinja2 would otherwise choke on the `:` in the token).

The date is sourced from the file's `ctime` (see above).

### Format tokens

| Token | Example output | Description |
|---|---|---|
| `YYYY` | `2026` | 4-digit year |
| `YY` | `26` | 2-digit year |
| `MM` | `03` | 2-digit month, zero-padded |
| `MMM` | `Mar` | 3-letter month abbreviation |
| `MMMM` | `March` | Full month name |
| `DD` | `13` | 2-digit day, zero-padded |
| `D` | `13` | Day without zero-padding |
| `HH` | `14` | 2-digit hour, 24-hour clock |
| `mm` | `30` | 2-digit minute |
| `ss` | `45` | 2-digit second |
| `dddd` | `Thursday` | Full day name |
| `ddd` | `Thu` | 3-letter day abbreviation |
| `[text]` | *(literal)* | Square-bracketed text is passed through verbatim (e.g. `[T]` → `T`, `[Moments]` → `Moments`) |

### Examples

```yaml
# Directory: 2026/03 Mar/
output_path_template: "{{DATE:YYYY/MM MMM}}"

# Filename: 260313-20260313_143000.md
output_filename_template: "{{DATE:YYMMDD}}-{{file_basename}}.md"

# ISO 8601 timestamp in frontmatter: 2026-03-13T143000
template: |
  ---
  date: {{DATE:YYYY-MM-DD[T]HHmmss}}
  ---

# Obsidian daily-note wikilink: [[Moments/2026/03 Mar/260313 Thursday]]
template: |
  ---
  dailynote: "[[{{DATE:[Moments]/YYYY/MM MMM/YYMMDD dddd}}]]"
  ---
```

Multiple `{{DATE:...}}` tokens can appear in the same string.

---

## Jinja2 features

All standard Jinja2 syntax is available: conditionals, loops, filters, whitespace control, etc.

```yaml
template: |
  ---
  {% if images %}coverimage: attachments/{{images[0].name}}{% endif %}
  ---
  {{llm_output}}

  {% if keywords %}
  ## Keywords
  {% for kw in keywords %}
  - {{ kw.content }}
  {%- endfor %}
  {% endif %}
```

See the [Jinja2 template designer docs](https://jinja.palletsprojects.com/en/stable/templates/) for the full syntax reference.
