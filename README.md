# SuperMD for macOS

A native macOS app that turns Supernote handwritten notes (`.note`, `.spd`)
plus PDFs and PNGs into Obsidian-ready Markdown using an LLM (cloud or local).

> **This branch is a fork in progress** — a SwiftUI-native rewrite of the
> existing Python CLI tool, designed to be the basis of a separate macOS-app
> repository. The Python conversion engine is kept as the engine of the app;
> the CLI you see in `src/supermd/` still works.

## Highlights

- **Native Mac UX** — SwiftUI app with drag-and-drop, menu-bar item, native
  notifications, and Settings tabs. Built as a signed `.app` bundle.
- **Cloud or local LLM, side by side** — paste an OpenAI/Anthropic/Gemini API
  key, or point at a local Ollama install. Switch per job.
- **Supernote Cloud sync built-in** — sign in once, the app handles the
  E1760 OTP flow inline and keeps a JWT cached for ~30 days.
- **Three Obsidian modes** — pick a vault and write straight into it; or write
  to a generic folder; or run Obsidian headless in the background.
- **Drag, watch, or sync** — drop files onto the app, point it at an Inbox
  folder (iCloud Drive, AirDrop's Downloads), or let it pull from Cloud.
- **Keeps the proven engine** — `src/supermd/` is the existing battle-tested
  pipeline; the app talks to it through a JSON-RPC sidecar.

## Repository layout

```
.
├── app/                 # SwiftUI macOS app  (SwiftPM, opens in Xcode)
├── sidecar/             # Python sidecar — JSON-RPC bridge to the engine
├── src/supermd/         # Python conversion engine (existing)
├── scripts/macos/       # Build / sign / DMG scripts
├── docs/macos/          # Architecture, dev, user guide
└── Makefile             # `make dev`, `make app`, `make dmg`, `make test`
```

## Quick start (development)

```bash
# 1. Install Python deps (engine + sidecar)
uv sync
uv pip install -e ./sidecar

# 2. Run the app in dev mode (uses python -m supermd_sidecar)
make dev
```

Open `app/Package.swift` in Xcode if you'd rather edit there.

## Building a distributable .app

```bash
make sidecar    # PyInstaller -> dist/macos/supermd-sidecar
make app        # swift build + assemble dist/macos/SuperMD.app
make dmg        # create-dmg -> dist/macos/SuperMD-x.y.z.dmg
```

Set `APPLE_TEAM_ID` to codesign automatically.

## Tests

```bash
make test            # all
make test-sidecar    # Python: sidecar/tests/
make test-engine     # Python: tests/  (the existing CLI/engine suite)
make test-app        # Swift: app/Tests/
```

CI workflow at `.github/workflows/macos-app.yml` runs all three on every push.

## Documentation

- [`docs/macos/ARCHITECTURE.md`](docs/macos/ARCHITECTURE.md) — How the app and
  sidecar fit together, the JSON-RPC wire format, where state lives.
- [`docs/macos/USER_GUIDE.md`](docs/macos/USER_GUIDE.md) — End-user walkthrough.
- [`docs/macos/DEVELOPMENT.md`](docs/macos/DEVELOPMENT.md) — Dev workflow,
  adding RPC methods, codesign + notarisation.
- [`sidecar/PROTOCOL.md`](sidecar/PROTOCOL.md) — Full JSON-RPC method list.

## Status

| Component | Status |
| --------- | ------ |
| Python engine (existing) | Stable |
| Sidecar JSON-RPC server  | Scaffolded; passing unit tests |
| Sidecar handlers (system, llm, obsidian, cloud, convert, config) | Scaffolded; passing unit tests |
| SwiftUI app shell | Scaffolded; needs UI polish + integration testing on real hardware |
| Build scripts (sidecar binary, .app, DMG) | Written; not yet exercised in CI |
| Codesign + notarisation | Wired up; needs an Apple Developer account to verify |

## Acknowledgements

Builds on the original [SuperMD CLI](https://github.com/rephlex00/supermd)
which kept the heavy lifting (Supernote format parsing, image extraction, LLM
orchestration, Jinja templating, metadata DB) sane for years. Ported and
wrapped, not rewritten.
