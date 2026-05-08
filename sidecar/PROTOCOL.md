# SuperMD Sidecar — JSON-RPC Protocol

Wire format: **JSON-RPC 2.0**, one JSON object per `\n`-terminated line, on
stdin/stdout. stderr is human-readable log output.

The sidecar can both **respond** to requests (`{"id": ..., "result": ...}`)
and **emit notifications** (`{"method": "...", "params": ...}` with no `id`).
The host listens for both.

## System

| Method            | Params              | Result                                   |
| ----------------- | ------------------- | ---------------------------------------- |
| `system.ping`     | —                   | `{ "pong": true, "version": "0.1.0" }`   |
| `system.shutdown` | —                   | `{ "ok": true }` (sidecar exits cleanly) |
| `system.config_path` | —                | `{ "path": "/.../config.yaml" }`         |

## LLM

| Method                  | Params                       | Result                                       |
| ----------------------- | ---------------------------- | -------------------------------------------- |
| `llm.list_models`       | —                            | `{ "api": [...], "ollama": [...] }`          |
| `llm.test_key`          | `{ "provider": "openai", "key": "..." }` | `{ "ok": true, "model": "gpt-4o-mini" }` |
| `llm.set_key`           | `{ "provider": "openai", "key": "..." }` | `{ "ok": true }` (writes to keychain) |
| `llm.ollama_status`     | —                            | `{ "running": true, "models": [...] }`       |

## Obsidian

| Method                    | Params                          | Result                                              |
| ------------------------- | ------------------------------- | --------------------------------------------------- |
| `obsidian.list_vaults`    | —                               | `{ "vaults": [{"id","name","path"}] }`              |
| `obsidian.open_note`      | `{ "vault": "...", "file": "..." }` | `{ "ok": true }` (uses `obsidian://` URI)       |
| `obsidian.start_headless` | `{ "vault_path": "..." }`       | `{ "pid": 12345 }`                                  |
| `obsidian.stop_headless`  | —                               | `{ "ok": true }`                                    |

## Supernote Cloud

Cloud sync is stateful — login may suspend on OTP. The flow is:

1. Host calls `cloud.login` with email/password.
2. If the account is on a new device, sidecar emits a `cloud.otp_required`
   notification and the `login` request remains *pending*.
3. Host shows an OTP sheet, user enters the code, host calls `cloud.submit_otp`.
4. The original `cloud.login` resolves with `{ "ok": true, "token": "..." }`.

| Method               | Params                                  | Result                                       |
| -------------------- | --------------------------------------- | -------------------------------------------- |
| `cloud.login`        | `{ "email": "...", "password": "..." }` | `{ "ok": true, "token": "..." }`             |
| `cloud.login_token`  | `{ "token": "..." }`                    | `{ "ok": true }` (use cached JWT, no OTP)    |
| `cloud.submit_otp`   | `{ "code": "123456" }`                  | `{ "ok": true }`                             |
| `cloud.list_remote`  | `{ "path": "/Note" }`                   | `{ "items": [...] }`                         |
| `cloud.start_sync`   | `{ "remote_path": "/Note", "local_path": "...", "interval_sec": 300 }` | `{ "task_id": "..." }` |
| `cloud.stop_sync`    | `{ "task_id": "..." }`                  | `{ "ok": true }`                             |
| `cloud.logout`       | —                                       | `{ "ok": true }` (clears token)              |

Notifications:

- `cloud.otp_required` `{ "email": "..." }` — host should show OTP sheet.
- `cloud.sync_progress` `{ "task_id": "...", "downloaded": 3, "queued": 0 }`
- `cloud.token_refreshed` `{ "token": "..." }` — host re-stores in keychain.

## Conversion

| Method                       | Params                                                                        | Result                              |
| ---------------------------- | ----------------------------------------------------------------------------- | ----------------------------------- |
| `convert.file`               | `{ "input": "...", "output": "...", "model": "...", "force": false, "config": {...} }` | `{ "task_id": "...", "queued": true }` |
| `convert.directory`          | `{ "input": "...", "output": "...", ... }`                                    | `{ "task_id": "...", "files": 17 }` |
| `convert.cancel`             | `{ "task_id": "..." }`                                                        | `{ "ok": true }`                    |
| `convert.list_active`        | —                                                                             | `{ "tasks": [...] }`                |
| `convert.rebuild_metadata`   | `{ "input": "...", "output": "..." }`                                         | `{ "ok": true, "rebuilt": 17 }`     |
| `convert.clean_metadata`     | `{ "output": "..." }`                                                         | `{ "ok": true }`                    |

Notifications:

- `convert.started` `{ "task_id": "...", "file": "...", "pages": 12 }`
- `convert.page` `{ "task_id": "...", "page": 4, "total": 12 }`
- `convert.finished` `{ "task_id": "...", "output_path": "...", "duration_ms": 8421 }`
- `convert.skipped` `{ "task_id": "...", "reason": "input_unchanged" }`
- `convert.failed` `{ "task_id": "...", "error": "...", "traceback": "..." }`
- `log.line` `{ "level": "INFO", "msg": "..." }` — mirror of engine log

## Config

| Method               | Params           | Result                            |
| -------------------- | ---------------- | --------------------------------- |
| `config.read`        | —                | `{ "yaml": "...", "data": {...} }` |
| `config.write`       | `{ "yaml": "..." }` | `{ "ok": true }`                |
| `config.defaults`    | —                | `{ "data": {...} }`              |
