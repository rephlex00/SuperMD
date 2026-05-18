# SuperMD for macOS — Development

## Prerequisites

- macOS 14+ (Sonoma) on Apple Silicon. Intel works but is not a release target.
- Xcode 15+ (with `xcode-select -s /Applications/Xcode.app/Contents/Developer` so `swift test` can find XCTest).
- Python 3.12 + [`uv`](https://github.com/astral-sh/uv).
- DMG packaging is done with `hdiutil` (built in); `create-dmg` is no longer required.

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
make sidecar     # PyInstaller -> dist/macos/supermd-sidecar (~56 MB single binary)
make app         # swift build -c release, copies sidecar into Resources/
                 #   -> dist/macos/SuperMD.app
make dmg         # hdiutil -> dist/macos/SuperMD-<version>.dmg (~57 MB)
make release     # all of the above (sidecar + app + dmg)
```

Setting `APPLE_TEAM_ID` to your Developer ID team makes `build-app.sh`
codesign the bundle (`codesign --force --deep --options runtime`). Without
it, the script ad-hoc-signs locally; the resulting bundle runs on your own
Mac but will be blocked by Gatekeeper on a freshly-downloaded copy.

**Notarisation** is not yet wired into the scripts. To notarise manually:

```bash
xcrun notarytool submit dist/macos/SuperMD-0.1.0.dmg \
    --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" \
    --keychain-profile "notarytool-password" --wait
xcrun stapler staple dist/macos/SuperMD-0.1.0.dmg
```

## Testing

- Engine: `pytest` (existing test suite, unchanged).
- Sidecar: `pytest sidecar/tests/` — drives the RPC loop with synthetic
  requests, mocks the engine.
- App: `swift test` from the `app/` directory.

The repo also ships `scripts/e2e_probe.py` — spawns the real sidecar as a
subprocess, drops a real `.note` through `convert.file` with the LLM stubbed,
and asserts `convert.started → convert.page → convert.finished` arrives over
real stdio framing. Run it after touching any RPC handler:

```bash
.venv/bin/python scripts/e2e_probe.py
```

For headless GUI testing, the app honors these env vars at launch:

| Var                              | Effect                                                 |
| -------------------------------- | ------------------------------------------------------ |
| `SUPERMD_REPO_ROOT`              | Pin the repo path the dev sidecar runs from           |
| `SUPERMD_TEST_OUTPUT=/path`      | Force output mode to folder + path                    |
| `SUPERMD_TEST_NO_INBOX=1`        | Skip the FSEvents inbox watcher (and its Documents-perms prompt) |
| `SUPERMD_TEST_DROP=a.note,b.note`| Inject a drop ~2s after launch                        |
| `SUPERMD_TEST_BODY_TEMPLATE_FILE=/path/template.md` | Pre-set the external body template      |

## Adding a new RPC method

1. Add a handler function in `sidecar/src/supermd_sidecar/handlers/<topic>.py`.
2. Register it in `handlers/__init__.py`'s dispatch table.
3. Add a typed wrapper in `app/Sources/SuperMD/Sidecar/SidecarClient.swift`.
4. Update `sidecar/PROTOCOL.md`.

Handlers must be idempotent and side-effect-free for RPC requests; long-running
work (conversion, cloud sync) is started by an RPC call but progresses via
notifications (`progress.update`, `log.line`, `cloud.otp_required`).
