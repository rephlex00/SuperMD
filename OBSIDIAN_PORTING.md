# SuperMD → Obsidian plugin

A pure-TypeScript port of SuperMD's conversion pipeline as an Obsidian community plugin,
living in [`obsidian-plugin/`](obsidian-plugin/). It runs on **desktop and mobile** (no
Node, no Python), decodes `.note` files itself, transcribes pages via an LLM, and writes
Markdown back into the vault. Independent of the on-device port (`device-plugin/`, which uses
the Supernote SDK's native rasterizer — not available here).

## Why this exists

Supernote `.note` files are often synced into an Obsidian vault, but Obsidian can't read or
render them. This plugin makes them first-class: viewable inline and convertible to Markdown,
entirely within Obsidian, on any platform it runs on.

## Architecture & reuse map

| Concern | Python source | TS module |
| --- | --- | --- |
| `.note` parse | `supernotelib/parser.py`, `fileformat.py` | `src/note/parser.ts`, `fileformat.ts` |
| Flate decode | `supernotelib/decoder.py` (FlateDecoder) | `src/note/decoders/flate.ts` (uses `pako`) |
| RattaRLE / X2 | `supernotelib/decoder.py` (RattaRle*) | `src/note/decoders/rattaRle.ts` |
| Layer compositing | `supernotelib/converter.py` (`_flatten_layers`) | `src/note/compositor.ts` |
| Palette | `supernotelib/color.py` | `src/note/color.ts` |
| Page → image | Pillow | `src/note/render.ts` (Canvas → data URL / PNG / `<img>`) |
| LLM call | `ai_utils.py` | `src/llm/client.ts` (`requestUrl`, OpenAI-compatible) |
| Orchestration | `converter.py` (rolling 50-char ctx, cooldown, skip/protect) | `src/pipeline/convert.ts` |
| Context / dates | `context.py` | `src/pipeline/context.ts` |
| Template + DATE tokens | `config.py`, `date_utils.py` | `src/pipeline/template.ts` (`nunjucks`), `dateTokens.ts` |
| Skip/protect store | `metadata_db.py` | `src/store/metadata.ts` (JSON + SHA-1) |
| Cloud sync | `docker/stack/supernote-sync/sync.py` (sncloud) | `src/cloud/snclient.ts`, `sync.ts`, `otpModal.ts` |
| Defaults / prompts | `config.py` | `src/config/defaults.ts` |

Obsidian surface: `src/main.ts` (commands, ribbon, file-menu, vault-event auto-convert,
cloud poll), `src/settings.ts` (settings tab), `src/view/noteView.ts` (file-explorer viewer),
`src/view/noteEmbed.ts` (`![[*.note]]` embed renderer), `src/secret.ts` (SecretStorage).

## Decoder notes (the central work)

- **FlateDecoder**: `pako.inflate`, interpret as uint16, reshape 1404×1888, rotate 90° CW,
  drop the bottom 16 rows, remap color codes → grayscale.
- **RattaRLE / X2**: faithful port of the byte-pair RLE state machine (holder/waiting-queue,
  `0xff`→`0x4000/0x400` markers, `&0x80` continuation, tail-length adjust); X2 chosen when
  the signature year ≥ `20230015`.
- **Compositor**: decode each layer by name, composite bottom-up per `LAYERSEQ`, treating
  `0xff` as transparent; visibility from `LAYERINFO`. Grayscale only.
- **Render**: grayscale → `Canvas` `ImageData`; downscale (~1568px) + JPEG for the LLM,
  lossless PNG for attachments, `<img>` for the viewer/embeds.

## Known limitations / to verify

- **Decoder validation**: the algorithms are ported faithfully and unit-tested on synthetic
  input, but need **golden-file tests against real `.note` files** (decode in Python via
  `supernote_tool` and byte-compare). Add a sample under `obsidian-plugin/fixtures/`.
- **Custom backgrounds**: `user_*` PNG page templates aren't decoded (treated as blank);
  handwriting layers render normally.
- **Supernote Cloud**: `login`/`ls`/`download` follow the long-standing public API; the
  **E1760 OTP and CSRF (`X-XSRF-TOKEN`) specifics should be verified against the `sncloud`
  fork** (`rnbennett/sncloud`) — the relevant endpoints are isolated in `cloud/snclient.ts`.
- **Secrets**: stored via Obsidian SecretStorage when available, else a plugin-dir JSON
  fallback (plaintext). The fallback path is clearly labeled in settings.

## Verification

```bash
cd obsidian-plugin
npm install && npm run build   # tsc clean + main.js
npm test                       # decoder / date-token / base64 units
```

Manual: copy `manifest.json` + `main.js` + `styles.css` into a test vault's
`.obsidian/plugins/supermd/`, enable it, set an API key, then: convert a `.note` (check the
`.md` + inline `![[file.note]]` render), open a `.note` from the explorer (viewer), toggle
auto-convert and drop a `.note` into the watch folder, and run a cloud sync.
