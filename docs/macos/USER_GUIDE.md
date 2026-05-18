# SuperMD for macOS — User Guide

## First launch

Open the app. You'll see the main window with an empty drop zone. Before
dropping anything, configure two things in **Settings** (⌘,):

1. **LLM** — pick a provider (OpenAI / Anthropic / Gemini / Ollama). For
   cloud providers, paste an API key and click **Test & save** — SuperMD
   makes a real 1-token probe to confirm the key works before storing it in
   macOS Keychain. For Ollama, run Ollama locally; SuperMD detects it on
   `127.0.0.1:11434`.
2. **Output** — pick where converted notes land:
   - **Pick a vault**: SuperMD reads your Obsidian vault list and offers a
     dropdown. Files go into `<vault>/<subfolder>/…`.
   - **Generic output folder**: pick any folder.
   - **Headless Obsidian** *(advanced)*: run obsidian-headless in the
     background against a vault so its plugins index new notes.

Optionally also set up:

- **General → Inbox folder** — a watched directory (default
  `~/Documents/Supernote Inbox`). Files saved here are converted
  automatically. Drop AirDrop or iCloud Drive landings here.
- **Cloud** — sign into Supernote Cloud. New-device verification (E1760)
  is handled inline: type the email code into the verification sheet.
  Token is cached for ~30 days.

## The main window

A header with status + Settings + pause buttons, optionally a colored
banner if the sidecar exited, then a two-pane split:

- **Conversion queue** (left) — every file SuperMD has seen this session
  with its current state:
  - **Queued** while waiting for the sidecar to start it
  - **Page X of Y** during conversion
  - **Done in Nms** with a green check on success
  - **Skipped — input_unchanged** when the file's hash matches a previous
    conversion; click the small `↻` button on the row to re-run it
    anyway (`force=true`)
  - **Failed — …** in red with the error
- **Log** (right) — last 200 lines from the sidecar with level coloring.
  Mirrors the engine's logging in real time.

**Right-click any row** for Run again, Cancel (if in flight), or
Remove from list.

## Menu bar

A small menu-bar item shows:

- ⏸ / ▶ Pause/resume conversion.
- **Open SuperMD** — surfaces the main window.
- **Quit**.

If **Settings → General → Hide from Dock** is on, the menu bar is the
only way to reach the app.

## Settings tabs

| Tab        | What lives here                                                                       |
| ---------- | ------------------------------------------------------------------------------------- |
| General    | Drag-and-drop on/off, Inbox folder + watch, run at login, hide from Dock, notifications |
| LLM        | Provider + model picker, API key (Keychain-stored), Ollama status, title generation, page cooldown |
| Cloud      | Supernote Cloud sign-in, auto-sync toggle, remote folder, sync interval               |
| Output     | Vault / generic-folder / headless mode, "Open in Obsidian after conversion"           |
| Templates  | Path / filename / body templates with a `{ }` token picker; load body from an external `.md` file (Obsidian Templates folder) |
| Advanced   | Sidecar log level, open log directory, direct edit of `supermd.yaml`                  |

## Template tokens

Click the `{ }` button next to any template field to see a menu of every
supported token grouped by category:

- **File**: `{{file_basename}}`, `{{title}}` (requires Generate Titles)
- **Date**: `{{DATE:YYYY-MM-DD}}`, `{{DATE:YYYY}}`, `{{DATE:MM}}`,
  `{{DATE:MMM}}`, `{{DATE:dddd}}`, `{{DATE:YYYY/MM MMM}}`, …
- **Body** (body templates only): `{{llm_output}}` (required somewhere in
  the body or your notes will be empty), `{{title}}`
- **Supernote metadata** (body templates only): `{{links}}`, `{{keywords}}`,
  `{{titles}}`, `{{images}}` — Jinja2 lists you can iterate

## External Markdown template file

In **Settings → Templates → Body template** switch the source picker to
**From file**. Point at any `.md` file (defaults to your active Obsidian
vault's Templates folder). The file is re-read on every conversion, so
edits made from inside Obsidian take effect on the next note — no
restart required.

The editor inside SuperMD mirrors the file with Save / Reload buttons.

## Keyboard shortcuts

| Action                 | Shortcut |
| ---------------------- | -------- |
| Pause/resume           | Space    |
| Force-reprocess selection | ⌘⇧R    |
| Cancel selection       | ⌘.       |
| Settings               | ⌘,       |

## Privacy and data

- Pages are sent to whichever LLM you pick. With Ollama, nothing leaves
  the Mac.
- API keys and Supernote Cloud passwords live in macOS Keychain (service
  `com.supermd.app`). The JWT token, once obtained, replaces the
  password for routine syncs.
- The app never phones home; there is no analytics or telemetry.

## Troubleshooting

- **App won't start / sidecar fails**: a red banner appears at the top
  with the exit code. Click **Restart Sidecar**. If it keeps failing,
  open **Settings → Advanced → Open log directory** for sidecar stderr.
- **"No output folder configured"**: open **Settings → Output** and
  pick a vault or generic folder.
- **Drop disappears**: check **Settings → General → Drag-and-drop**.
  Unsupported file types now show a visible failed row instead of being
  silently dropped — only `.note`, `.spd`, `.pdf`, `.png` are accepted.
- **Skipped jobs**: SuperMD hashes every input. A second pass over the
  same file is skipped to save tokens. Click the `↻` button on the
  skipped row to force a re-run.
