# Porting SuperMD onto the Supernote device

This document is the architecture & roadmap for running SuperMD's note→Markdown
conversion **on the Supernote tablet itself**, as a plugin built with the official
`sn-plugin-lib` SDK. The Python tool in `src/supermd/` remains the server/desktop product;
this is a parallel on-device port.

## Why & what

SuperMD today rasterizes Supernote notes and transcribes each page to Markdown via an LLM,
running off-device (CLI / watcher / Docker). The goal here is to do that conversion
**on the device**, auto-triggered when the user finishes writing, with a manual option too,
writing the resulting `.md` to the synced Obsidian vault.

The plugin runtime is **React Native / TypeScript** on Android-based Linux (ARM, e-ink,
2–4 GB RAM). Python cannot run there, so the on-device port is TypeScript.

## What the spike found (the SDK is far more capable than public docs)

Reading the bundled type definitions in `sn-plugin-lib@0.1.43`
(`node_modules/sn-plugin-lib/lib/typescript/src/`) revealed a real, structured SDK. The
single most important consequence:

> **`PluginFileAPI.generateNotePng({ notePath, page, times, pngPath, type })` rasterizes a
> note page to PNG natively on the device.** This **eliminates the highest-risk item** in
> the original plan — we do **not** port the vendored `supernotelib` RLE/Flate decoder,
> compositor, or PNG encoder. The device produces the page bitmap for us.

Other load-bearing SDK surface (all return an `APIResponse`-shaped object
`{ success, result, error }`):

| Need | SDK call |
| --- | --- |
| Page bitmap | `PluginFileAPI.generateNotePng(...)` (also `generateNoteTemplatePng`, `generateMarkThumbnails`) |
| Page count | `PluginFileAPI.getNoteTotalPageNum(notePath)` |
| Page size / device type | `PluginFileAPI.getPageSize`, `getFileMachineType`; `PluginManager.getDeviceType()` |
| Titles / keywords / links | `PluginFileAPI.getTitles`, `getKeyWords`, `getElements` (strokes, links, titles, text) |
| Document (PDF) text | `PluginDocAPI.getCurrentDocText(page)`, `getCurrentTotalPages`, `getLastSelectedText` |
| Manual trigger UI | `PluginManager.registerButton(type, ['NOTE'], button)` + `ButtonListener` (type 1=sidebar, 2=lasso, 3=doc-selection) |
| Live event | `PluginManager.registerEventListener('event_pen_up', regType, listener)` — **only `event_pen_up` is supported; there is no save hook** |
| Save current note | `PluginNoteAPI.saveCurrentNote()` |
| Write back to note | `PluginNoteAPI.insertImage(pngPath)`, `insertText(...)`, `PluginFileAPI.insert/replace/modifyElements` |
| Plugin dir (SYNCED) | `PluginManager.getPluginDirPath()` — secrets must **not** be stored here |
| Lifecycle / view | `addPluginLifeListener`, `showPluginView`, `closePluginView` |

**Still requires empirical confirmation on hardware (that's the spike's job):**
1. **Outbound `fetch`** to a cloud LLM (existential — `device-plugin/spike` P2).
2. `generateNotePng` actually works and is fast enough (P3) — confirms the de-risking above.
3. Writing to the actual Obsidian vault path under Android scoped storage (P4).
4. `react-native-keychain` is device-local and not synced into the plugin dir (P7).
5. `react-native-tcp-socket` can bind a port for the onboarding server (P6).
6. *(future, non-gating)* `event_pen_up` fires / polling-scan cost (P5) — only relevant to
   the optional Phase 4 auto-trigger; the initial scope is fully manual.

## Phase 0 — Spike (in `device-plugin/spike/`, done)

A throwaway RN/TS plugin with 8 probes (P1–P8) that answer the questions above on real
hardware. Each writes a pass/fail line to the screen and to
`${DocumentDirectory}/supermd-spike.log` — read that file back over USB/sync to record
results here. **Decision gate:** P2, P3, P4, P7 must pass to start Phase 1. See
`device-plugin/README.md` to build and run it.

## Phase 1+ — Full port (after the spike validates on hardware)

Module-by-module mapping, **revised for the native rasterizer**:

| Python | TS counterpart | Approach | Risk |
| --- | --- | --- | --- |
| `supernotelib/*` decoder + `importers/note.py` | *(dropped)* | use `PluginFileAPI.generateNotePng` | **eliminated** |
| `ai_utils.py` | `llm/client.ts` | `fetch` → OpenAI-compatible `/chat/completions`, base64 image data URI; key from keychain | Low |
| `converter.py` orchestration | `pipeline/convert.ts` | per-page loop: `generateNotePng` → read PNG → downscale/encode → LLM → accumulate; keep the rolling 50-char context and `cooldown` from the Python version | Medium |
| `context.py` | `pipeline/context.ts` | filename-date regex + mtime fallback; titles/keywords/links from `getTitles`/`getKeyWords`/`getElements` instead of binary parsing | Low |
| Jinja2 template + `date_utils.py` | `pipeline/template.ts` | `nunjucks` + a `{{DATE:...}}` regex pre-pass | Medium |
| `config.py` | `config/schema.ts` + `defaults.ts` | `zod`; keep default prompt/template constants | Low |
| `metadata_db.py` | `store/metadata.ts` | JSON file in `<vault>/.meta/` via RNFS; SHA-1 (or size+mtime) for skip/protect; `ignoresnlock` opt-out | Medium |
| *(new)* durable conversion queue | `store/queue.ts` + `pipeline/runner.ts` | persistent JSON queue; all-or-nothing per note; auto-retry w/ backoff + manual retry/remove; drains on next runtime when online | Medium |
| `watcher.py` (auto-trigger) | *(deferred — not in initial scope)* | optional later: pen-up debounce / foreground polling enqueue into the queue | — |
| `gui.py` | `onboarding/server.ts` + `www/` | ephemeral `react-native-tcp-socket` HTTP server, on-screen pairing token | Med-High |
| `importers/pdf.py` (PDF) | optional | `PluginDocAPI.getCurrentDocText` / `generateDocImage` (native) | Low if pursued |
| `importers/atelier.py`, SVG, `cmds/` | *(dropped on-device)* | — | — |

### Conversion trigger — fully manual + a durable queue (initial scope)

Triggering is **completely manual** in the initial scope. There is no auto-trigger
(pen-up / polling) — that's deferred (see Phase 4, optional). The user explicitly asks for
a conversion; the work is then **queued and persisted** so it survives the device being
offline or the plugin closing, and runs on the next runtime.

- **Manual action:** register a sidebar button (`registerButton(1, ['NOTE'], ...)`) and a
  list UI. On "Convert", `saveCurrentNote()` (if it's the open note), then **enqueue** the
  note path — do not block on the LLM.
- **Durable queue** (`store/queue.ts`): a JSON file in `<vault>/.meta/supermd.queue.json`
  (durability relies on the writable storage validated by spike P4/P7). Each item:
  `{ notePath, inputHash, status: 'queued'|'processing'|'failed'|'done', attempts,
  nextAttemptAt, lastError }`.
- **Processing model — all-or-nothing per note:** a note's `.md` is written only when
  **all** pages transcribe successfully. If interrupted (offline mid-note), nothing is
  written; the item returns to `queued` and is retried **whole** next time. No partial
  files are ever produced.
- **Runner lifecycle:** on plugin start (and after each manual trigger), a single-flight
  runner drains the queue while online — for each item: rasterize → LLM per page →
  template → write `.md`. On network failure it stops cleanly, leaving items `queued`.
- **Retry policy — auto + manual:** failed/offline items auto-retry on the next runtime and
  after an exponential backoff (`nextAttemptAt`). The queue UI shows per-item status and
  offers **Retry now** and **Remove**. Online-ness is detected by attempting the call
  (and/or a cheap reachability check); no true background execution is possible.

### LLM, keys & onboarding
- LLM via on-device `fetch`. **API key encrypted at rest in `react-native-keychain`**
  (device-local, NOT in the synced plugin dir from `getPluginDirPath()`).
- Ephemeral onboarding web server (only while on the Settings screen): user points a phone
  browser at `http://<deviceIP>:<port>` (shown on e-ink with a pairing token) and enters
  the key + config. Key → keychain; non-secret config → `<vault>/.meta/supermd.config.json`.
  Mirrors the existing Python `gui.py`. Caveat: key is briefly cleartext over LAN HTTP —
  acceptable for an ephemeral, token-gated, home-network flow; document it.

### Output
Write `.md` + downscaled image attachments to the Obsidian vault/output path via RNFS;
this syncs to other devices. Optionally also `insertImage`/`insertText` the result back into
the note so it's visible on the e-ink device (gated by spike P8).

### Performance (constrained ARM e-ink)
- Page-at-a-time streaming; never hold all pages. Free the PNG buffer between pages.
- LLM latency dominates; native `generateNotePng` is the device's own optimized path.
- Downscale the page (~1568 px longest edge) + JPEG for the LLM upload to cut latency/tokens
  while keeping handwriting legible.

### Phased delivery
1. **Phase 1 — manual + durable queue MVP:** sidebar button enqueues the note; a runner
   drains the persistent queue when online — `generateNotePng` per page → `fetch` LLM with
   rolling context → `nunjucks` template → write `.md`+attachments (all-or-nothing per
   note). Auto-retry on next runtime + a basic queue/status UI. Key from keychain
   (temporary in-app field).
2. **Phase 2 — batch + skip/protect:** convert-all enqueues many notes, metadata store
   (JSON), hashing, `ignoresnlock`, attachment cleanup; pull titles/keywords/links from
   the SDK.
3. **Phase 3 — onboarding web config:** ephemeral HTTP server, port the `gui.py` form,
   key→keychain, config→RNFS JSON.
4. **Phase 4 (optional, later) — auto-trigger:** pen-up debounce / foreground polling that
   simply *enqueues* into the same queue + `saveCurrentNote`. Optional: write-back into the
   note via `insertImage`. Not part of the initial scope.

## Spike results (fill in after running on hardware)

| Probe | Question | Result |
| --- | --- | --- |
| P1 | SDK bridge init / device / plugin dir | _pending_ |
| P2 | Outbound HTTPS fetch (existential) | _pending_ |
| P3 | `generateNotePng` rasterizes a page | _pending_ |
| P4 | Write to vault path | _pending_ |
| P5 | `event_pen_up` fires; polling cost | _pending_ |
| P6 | Ephemeral HTTP server binds | _pending_ |
| P7 | Keychain device-local & non-synced | _pending_ |
| P8 | Native titles/keywords; insertImage | _pending_ |

**Reference Python sources** (behavioral spec for the TS port):
`src/supermd/converter.py` (orchestration, rolling context, cooldown, skip/protect),
`src/supermd/context.py` (dates + metadata), `src/supermd/ai_utils.py` (LLM call shape),
`src/supermd/config.py` (default prompt/template), `src/supermd/gui.py` (web config).
