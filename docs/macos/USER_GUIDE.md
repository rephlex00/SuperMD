# SuperMD for macOS — User Guide

## First launch

On first launch you see a four-step onboarding sheet:

1. **Choose your input.** Pick any combination:
   - Drag-and-drop only (no folders watched).
   - **Inbox folder** — defaults to `~/Documents/Supernote Inbox`. Anything
     dropped here is converted automatically.
   - **Supernote Cloud** — sign in with your Supernote account email and
     password. New-device verification is handled inside the app: you'll get a
     code by email and type it into the verification sheet. Token is then
     cached for ~30 days.

2. **Choose your output.** Pick one:
   - **Obsidian vault** — the app reads your Obsidian vault list and offers a
     dropdown. Pick a subfolder, optionally check "Open notes after
     conversion".
   - **Output folder** — pick any folder; you'll wire Obsidian up yourself.
   - **Headless Obsidian** *(advanced)* — point at an Obsidian vault and let
     the app run Obsidian in the background so Sync/Dataview keep up.

3. **Choose your model.** Pick one of:
   - Cloud (OpenAI / Anthropic / Gemini) + paste an API key.
   - Local (Ollama). The app detects Ollama; click **Pull a model** to grab
     a vision-capable one (e.g. `qwen2.5-vl:7b`, `llama3.2-vision:11b`).

4. **Review template.** Default frontmatter is:
   ```yaml
   ---
   created: 2026-05-08
   tags: supernote
   source: supernote
   ---
   ```
   The body template, path template, and filename template are all editable
   later in **Settings → Templates**.

## The main window

The main window is a single pane with three areas:

- **Inbox queue** — files waiting to be processed, currently processing
  (with per-page progress), and the last 50 done.
- **Failures** — anything that errored. Click to see the full traceback or
  re-queue.
- **Tail of the log** — last 200 lines from the sidecar. Click "Open log file"
  to view the full log in Console.app.

Clicking a finished file opens the resulting `.md` in Obsidian (if vault mode)
or in your default Markdown editor.

## Menu bar

A small menu-bar item shows:
- ⏸ / ▶ Pause/resume conversion.
- Cloud sync status (last poll, files queued).
- "Open SuperMD" / "Quit".

This means the app can be hidden from the dock if the user toggles the "Run in
background" preference.

## Settings tabs

| Tab        | What lives here                                                                    |
| ---------- | ---------------------------------------------------------------------------------- |
| General    | Inbox folder, drag-and-drop on/off, run at login, run in background, notifications |
| LLM        | API providers (key + default model), Ollama probe, model picker                    |
| Cloud      | Supernote Cloud account, sync interval, remote path, OTP re-verify button          |
| Obsidian   | Vault picker, "Open notes after conversion", per-folder mappings                   |
| Templates  | Frontmatter, body, path, filename templates with live preview                      |
| Advanced   | Sidecar log level, force-reprocess, rebuild metadata, view config.yaml             |

## Per-folder mappings

In **Obsidian → Per-folder mappings** the user can set rules like:

| Source (Inbox subfolder or Cloud path) | Vault destination       |
| -------------------------------------- | ----------------------- |
| `Inbox/Journal/`                       | `Daily Notes/{{DATE:YYYY-MM}}/` |
| `Inbox/Meetings/`                      | `Work/Meetings/`        |
| `Cloud:/Note/`                         | `Supernote/`            |

Mappings are pure Jinja2 with `{{DATE:...}}` tokens — same engine the CLI
uses.

## Keyboard shortcuts

| Action                 | Shortcut          |
| ---------------------- | ----------------- |
| New conversion (open)  | ⌘O                |
| Pause/resume           | Space (in window) |
| Force reprocess        | ⌘⇧R               |
| Open settings          | ⌘,                |
| Show in Finder         | ⌘⌥R (on a row)    |
| Open in Obsidian       | ⌘O (on a row)     |

## Privacy and data

- Pages are sent to whichever LLM you pick. With Ollama, nothing leaves the
  Mac.
- Supernote Cloud credentials live in macOS Keychain. The JWT token, once
  obtained, replaces the password for routine syncs.
- The app never phones home; there is no analytics or telemetry.
