# SuperMD for Obsidian

Convert and view Supernote `.note` files inside your Obsidian vault — a pure-TypeScript
port of [SuperMD](../README.md) that runs on **desktop and mobile** (no Python, no Node).

## Features

- **Decode `.note` in-app** — a pure-TS port of the Supernote decoder (zlib + RattaRLE/X2 +
  layer compositing) renders pages with no external tools.
- **Direct viewing** — open a `.note` from the file explorer to see its pages, and embed one
  inline anywhere with `![[file.note]]` (rendered live by the plugin).
- **LLM transcription** — each page is transcribed to Markdown via an OpenAI-compatible
  vision endpoint (`requestUrl`, so it works on mobile and avoids CORS), with the same
  rolling-context, cooldown, prompt, and template behavior as SuperMD.
- **Two output modes** — embed the original `.note` at the end of the generated note
  (default), or extract per-page PNG attachments.
- **Triggers** — command palette, ribbon, right-click file menu, and optional auto-convert on
  vault `create`/`modify` (debounced, optionally limited to a watch folder).
- **Supernote Cloud sync** — log in (with the E1760 new-device OTP flow) and pull `.note`
  files into a vault folder, manually or on a periodic poll. Credentials live in the OS
  keychain via Obsidian SecretStorage.
- **Skip / protect** — unchanged inputs are skipped; hand-edited outputs are protected unless
  the note has `ignoresnlock: true` in its frontmatter.

## Build & install (for development)

```bash
cd obsidian-plugin
npm install
npm run build      # tsc --noEmit + esbuild → main.js
npm test           # decoder / date-token / base64 unit tests
```

Copy `manifest.json`, `main.js`, and `styles.css` into
`<vault>/.obsidian/plugins/supermd/`, then enable **SuperMD** in Community Plugins. Set your
LLM API key (and, optionally, Supernote Cloud credentials) in the plugin settings.

## Usage

- **Convert:** open a `.note` and run *“SuperMD: Convert active .note to Markdown”* (or use
  the ribbon / right-click menu).
- **View only:** *“SuperMD: Map active .note for viewing only”* writes a no-LLM stub that
  embeds the `.note`.
- **Cloud:** set your account in settings → *“Sync from Supernote Cloud”* (or enable
  auto-poll).

## Known limitations

See [`../OBSIDIAN_PORTING.md`](../OBSIDIAN_PORTING.md). In short: custom (user-image) page
backgrounds aren't decoded yet; the decoder needs golden-file validation against real
`.note` files; and the Supernote Cloud OTP/CSRF endpoints should be verified against the
`sncloud` fork.
