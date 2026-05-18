# SuperMD for macOS — Architecture

A native macOS app that turns Supernote handwritten notes into Obsidian-ready
Markdown using either an API LLM (OpenAI / Anthropic / Gemini) or a local model
via Ollama.

The app is a thin SwiftUI shell over the existing, battle-tested Python
conversion engine. The two halves talk over a JSON-RPC stdio pipe.

```
┌──────────────────────────────────────────────────────────┐
│                    SuperMD.app (SwiftUI)                 │
│                                                          │
│   Inbox / Queue   Settings   Onboarding   Menu bar item  │
│         │             │           │             │        │
│         └─────────────┴─SidecarManager─┴───────-┘        │
│                          │                               │
│                          │  JSON-RPC over stdio          │
│                          ▼                               │
│   ┌────────────────────────────────────────────────────┐ │
│   │     supermd-sidecar  (Python, bundled binary)      │ │
│   │                                                    │ │
│   │   handlers/convert.py      ──▶ supermd.converter   │ │
│   │   handlers/cloud.py        ──▶ sncloud (OTP flow)  │ │
│   │   handlers/llm.py          ──▶ llm provider probe  │ │
│   │   handlers/obsidian.py     ──▶ vault discovery     │ │
│   └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

## Why this split

- **Supernote parsing is heavy Python.** `supernotelib`, `atelier`, and
  `PyMuPDF` are mature. Re-implementing them in Swift would take weeks and
  introduce bugs. So the Python core stays.
- **macOS UX should feel native.** SwiftUI gives us proper windows, menus,
  preferences, drag-and-drop, Shortcuts, notifications, Keychain, and an icon
  in the dock or menu bar.
- **Process isolation buys us crash safety.** A bad PDF that segfaults the
  Python side won't take down the app — the SidecarManager just respawns it.

## Process model

There is exactly **one sidecar process** per app launch. It runs for the life
of the app, owns:

- the metadata SQLite DB,
- the Supernote Cloud client (with cached JWT),
- an in-flight conversion queue,
- file watchers for the user's Inbox folder.

The Swift app talks to it through:

| Direction | Channel  | Format                 |
| --------- | -------- | ---------------------- |
| App → Sidecar | stdin   | JSON-RPC 2.0 request   |
| Sidecar → App | stdout  | JSON-RPC 2.0 response or notification |
| Sidecar → App | stderr  | log lines (debug only) |

Notifications from sidecar → app are how progress, log lines, and OTP prompts
are streamed back to the UI in real time.

See `sidecar/PROTOCOL.md` for the full RPC method list.

## Input modes (how Supernote files arrive)

Configured in **Settings → General**:

1. **Drag-and-drop** (default on). Drop a `.note`, `.spd`, `.pdf`, or `.png`
   onto the app window or dock icon. Toggle to disable.
2. **Watched Inbox folder.** Defaults to `~/Documents/Supernote Inbox`. Can be
   pointed at iCloud Drive, Dropbox, or AirDrop's Downloads folder. The app
   uses `FSEvents` to react. The watcher is started on a background queue so
   the first-launch Documents-folder permission prompt doesn't block the main
   thread / main window.
3. **Supernote Cloud sync.** The sidecar polls `cloud.supernote.com` via the
   `sncloud` library used by the Docker stack. The E1760 new-device OTP flow
   is surfaced as a SwiftUI sheet. Auto-sync toggle in **Settings → Cloud**
   wires the `cloud.start_sync` / `cloud.stop_sync` RPCs.

## Output modes (how Markdown lands)

The user picks **one** in **Settings → Output**:

1. **Pick a vault** *(default).* The app reads the Obsidian-managed
   `~/Library/Application Support/obsidian/obsidian.json` to list local vaults,
   the user picks one, output writes straight to a folder inside it. Optional:
   open the freshly-written note via the `obsidian://open` URI scheme.
2. **Generic output folder.** Just write Markdown anywhere. The user wires it
   into Obsidian themselves.
3. **Headless Obsidian background service** *(advanced).* The app spawns
   Obsidian.app with `--no-sandbox --disable-gpu` and a dedicated profile so
   plugins (Sync, Dataview indexing, etc.) actually run while files appear.
   Useful for Obsidian Sync subscribers.

## Output customisation

Every option from the existing engine remains exposed in **Settings →
Templates**:

- Path template     (default `{{DATE:YYYY/MM MMM}}/{{file_basename}}`)
- Filename template (default `{{file_basename}}.md`)
- Frontmatter / body template (default ships an Obsidian-friendly frontmatter
  block with `created`, `tags`, `source: supernote`). Can be backed by an
  external `.md` file (typically in an Obsidian vault's Templates folder)
  that the engine re-reads on every conversion.
- Per-page LLM instruction (the prompt sent with each page image).
- Every editable template field has a `{ }` token-picker menu listing each
  supported token with a one-line description (categorised: File / Date /
  Body / Supernote metadata).

## LLM configuration

**Settings → LLM** has two columns: API providers, and Local (Ollama).

- API: pick a provider, paste a key, click **Test & save**. A 1-token probe
  against the live API confirms the key works *before* it's written to
  Keychain (service `com.supermd.app`). A green badge shows when a key is
  stored for the active provider.
- Local: the app probes `http://localhost:11434/api/tags` and lists installed
  Ollama models. Ollama runs outside of SuperMD; SuperMD only talks to it.

The user picks one as the **default model**. Every `convert.file` RPC
includes the current settings (template, prompt, model, cooldown, optional
title-generation prompt) so the engine sees the same config it would from
the YAML.

## Where settings live

| Setting kind           | Storage                                                                        |
| ---------------------- | ------------------------------------------------------------------------------ |
| UI prefs (window size) | `UserDefaults` (`~/Library/Preferences/com.supermd.app.plist`)                 |
| App config             | `~/Library/Application Support/SuperMD/config.yaml` (round-tripped via ruamel) |
| Conversion metadata    | `~/Library/Application Support/SuperMD/metadata.sqlite`                        |
| Secrets                | macOS Keychain (`com.supermd.app` service)                                     |
| Logs                   | `~/Library/Logs/SuperMD/sidecar.log` (rotated)                                 |

The on-disk YAML is the same shape as the CLI's `supermd.yaml`, so the engine
can be invoked headlessly with the same file. Power users can edit it
directly.

## Resilience

A few intentionally-defensive patterns:

- **Sidecar crash detection.** `SidecarManager` installs a
  `terminationHandler`; on exit it rejects every pending RPC continuation
  with `SidecarError.notRunning` and notifies the delegate. AppModel flips
  every queued / running row to `.failed("Sidecar exited")` and surfaces a
  tinted banner in the main window with a **Restart Sidecar** button.
- **ObjC-exception bridge.** `UNUserNotificationCenter.current()` aborts the
  process via `NSInternalInconsistencyException` from unsigned / untrusted
  bundles. A tiny Obj-C target (`SuperMDObjC`) wraps `@try`/`@catch` so the
  `Notifier` can probe it once and disable itself instead of crashing.
- **Nil-stdin RPC errors.** If a `sidecar.client.call(...)` runs against a
  manager whose stdin is gone (process exited), it throws
  `SidecarError.notRunning` instead of silently dropping the write.
- **Settings persistence forwarding.** `AppModel`'s nested
  `@Published var queue` / `@Published var settings` ObservableObjects
  forward their `objectWillChange` to the outer model — without this,
  SwiftUI views observing `AppModel` don't see queue-row updates or
  Settings-Choose-dialog edits.

## Distribution

Built as a signed, notarised `.app` bundle. Two deliverables:

- `SuperMD-x.y.z.dmg`              — drag-to-Applications installer.
- `SuperMD-x.y.z-arm64.tar.gz`     — Homebrew Cask source.

The bundled Python sidecar is built with PyInstaller into a single binary
(`Contents/Resources/supermd-sidecar`). All llm plugins (`llm-ollama`,
`llm-gemini`, `llm-claude-3`, etc.) are pre-installed in the bundle. No
`pip install` ever runs on the user's machine.

App Store distribution is **not** a goal — sandboxing would block the Ollama
IPC and the Python subprocess.
