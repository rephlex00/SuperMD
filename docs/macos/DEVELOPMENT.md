# SuperMD for macOS — Development

## Prerequisites

- macOS 14+ (Sonoma) on Apple Silicon. Intel works but is not a release target.
- Xcode 15+ (for the SwiftUI app).
- Python 3.12 + [`uv`](https://github.com/astral-sh/uv).
- For DMG packaging: `brew install create-dmg`.

## Layout

```
.
├── src/supermd/         # Python conversion engine (existing, kept verbatim)
├── sidecar/             # Python sidecar — JSON-RPC bridge over the engine
├── app/                 # SwiftUI macOS app (SwiftPM package)
├── scripts/macos/       # Build / sign / notarise / DMG scripts
└── docs/macos/          # These docs
```

## Quick start

```bash
# 1. Install Python deps for engine + sidecar
uv sync
uv pip install -e ./sidecar

# 2. Run the sidecar standalone (chats over stdin/stdout)
python -m supermd_sidecar

# In another terminal, send it a request:
echo '{"jsonrpc":"2.0","id":1,"method":"system.ping"}' | python -m supermd_sidecar

# 3. Build & run the SwiftUI app in dev mode
make dev
# (equivalently: ./scripts/macos/dev.sh)
```

`make dev` does:
- builds the sidecar with `swift build` env pointing at `python -m supermd_sidecar`,
- runs the app from the SwiftPM build dir,
- streams sidecar logs to the terminal.

## Talking to the sidecar by hand

The sidecar speaks JSON-RPC 2.0 framed by newlines (one JSON object per line).
Smoke test:

```bash
python -m supermd_sidecar <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"system.ping"}
{"jsonrpc":"2.0","id":2,"method":"obsidian.list_vaults"}
{"jsonrpc":"2.0","id":3,"method":"llm.list_models"}
EOF
```

Full method list: `sidecar/PROTOCOL.md`.

## Building a release

```bash
make sidecar     # PyInstaller -> dist/supermd-sidecar (single binary)
make app         # swift build -c release, copies sidecar into Resources/
make dmg         # create-dmg -> dist/SuperMD-<version>.dmg
make release     # all of the above + codesign + notarytool submit
```

Codesigning requires `APPLE_TEAM_ID` and a Developer ID Application cert in
the login keychain. Notarisation requires `APPLE_ID`, `APPLE_TEAM_ID`, and an
app-specific password stored in keychain as `notarytool-password`.

## Testing

- Engine: `pytest` (existing test suite, unchanged).
- Sidecar: `pytest sidecar/tests/` — drives the RPC loop with synthetic
  requests, mocks the engine.
- App: `swift test` from the `app/` directory.

There is no end-to-end test bot; manual smoke-testing flow is in
`docs/macos/SMOKE_TEST.md`.

## Adding a new RPC method

1. Add a handler function in `sidecar/src/supermd_sidecar/handlers/<topic>.py`.
2. Register it in `handlers/__init__.py`'s dispatch table.
3. Add a typed wrapper in `app/Sources/SuperMD/Sidecar/SidecarClient.swift`.
4. Update `sidecar/PROTOCOL.md`.

Handlers must be idempotent and side-effect-free for RPC requests; long-running
work (conversion, cloud sync) is started by an RPC call but progresses via
notifications (`progress.update`, `log.line`, `cloud.otp_required`).
