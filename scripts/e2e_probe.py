"""Live end-to-end probe: spawn the real sidecar subprocess, drive it the
way the Swift SidecarClient would, and verify a real .note runs through to
a markdown file with the full notification stream.

The LLM call is stubbed inside the subprocess (no network, no cost) so this
exercises: real stdio framing + real supernotelib parsing + real engine
metadata DB + real notification ordering.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "sidecar/tests/fixtures/sample.note"

LAUNCHER = r"""
import sys
from supermd import ai_utils
ai_utils.image_to_markdown = lambda image_path, context, model, prompt, ctx_dict: "# stub page from " + str(image_path) + "\n"
ai_utils.validate_model_key = lambda model: None
from supermd_sidecar.__main__ import main
sys.exit(main())
"""


def main() -> int:
    assert FIXTURE.exists(), f"missing fixture {FIXTURE}"
    tmp = Path(tempfile.mkdtemp(prefix="supermd-e2e-"))
    out = tmp / "out"
    out.mkdir()
    print(f"[probe] output -> {out}")

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO}/sidecar/src:{REPO}/src:" + env.get("PYTHONPATH", "")
    env["SUPERMD_CONFIG_DIR"] = str(tmp / "cfg")
    env["XDG_CONFIG_HOME"] = str(tmp / "cfg")
    env["XDG_DATA_HOME"] = str(tmp / "data")
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [str(REPO / ".venv/bin/python"), "-c", LAUNCHER],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, text=True, bufsize=1,
    )
    stderr_lines: list[str] = []
    threading.Thread(
        target=lambda: [stderr_lines.append(l.rstrip()) for l in proc.stderr],
        daemon=True,
    ).start()

    notifications: list[dict] = []
    responses: dict[int, dict] = {}

    def reader():
        for line in proc.stdout:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in obj and obj["id"] is not None:
                responses[obj["id"]] = obj
            else:
                notifications.append(obj)
                m = obj.get("method", "?")
                p = obj.get("params", {})
                print(f"[notif] {m} {json.dumps(p)[:140]}")
    threading.Thread(target=reader, daemon=True).start()

    def send(req: dict):
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()

    def wait_response(rid: int, timeout: float = 5.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if rid in responses:
                return responses[rid]
            time.sleep(0.02)
        raise TimeoutError(f"no response for id={rid}")

    def wait_notif(method: str, timeout: float = 30.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for n in notifications:
                if n.get("method") == method:
                    return n
            time.sleep(0.05)
        raise TimeoutError(f"never saw {method}")

    try:
        # 1) ping
        send({"jsonrpc": "2.0", "id": 1, "method": "system.ping"})
        ping = wait_response(1)
        print(f"[probe] ping -> {ping['result']}")

        # 2) convert.file
        send({
            "jsonrpc": "2.0", "id": 2, "method": "convert.file",
            "params": {
                "input": str(FIXTURE),
                "output": str(out),
                "config": {"defaults": {"cooldown": 0}},
            },
        })
        resp = wait_response(2)
        print(f"[probe] convert.file response -> {resp.get('result') or resp.get('error')}")
        task_id = resp["result"]["task_id"]

        # 3) wait for terminal notification
        deadline = time.monotonic() + 60
        terminal = None
        while time.monotonic() < deadline:
            for n in notifications:
                m = n.get("method")
                if m in ("convert.finished", "convert.skipped", "convert.failed") \
                   and n["params"].get("task_id") == task_id:
                    terminal = n
                    break
            if terminal:
                break
            time.sleep(0.1)
        if not terminal:
            print("[probe] FAIL: no terminal notification")
            return 1
        print(f"[probe] terminal -> {terminal['method']} {terminal['params']}")

        # 4) verify markdown on disk
        mds = list(out.rglob("*.md"))
        print(f"[probe] markdown files: {[str(p.relative_to(out)) for p in mds]}")
        if not mds:
            print("[probe] FAIL: no .md produced")
            return 1
        sample = mds[0].read_text()
        print(f"[probe] first md (first 200 chars):\n{sample[:200]}")

        # 5) verify started + at least one page notification
        kinds = [n["method"] for n in notifications]
        started_ok = "convert.started" in kinds
        page_ok = "convert.page" in kinds
        print(f"[probe] saw convert.started={started_ok} convert.page={page_ok}")

        # 6) ordered shutdown
        send({"jsonrpc": "2.0", "id": 99, "method": "system.shutdown"})
        try:
            proc.wait(timeout=3)
            print(f"[probe] sidecar exited cleanly rc={proc.returncode}")
        except subprocess.TimeoutExpired:
            print("[probe] WARN: sidecar didn't exit on shutdown RPC")
            proc.terminate()

        ok = (terminal["method"] == "convert.finished" and mds and started_ok)
        print("\n=== RESULT:", "PASS" if ok else "FAIL", "===")
        if stderr_lines:
            print("\n[stderr tail]")
            for l in stderr_lines[-20:]:
                print(" ", l)
        return 0 if ok else 1
    finally:
        if proc.poll() is None:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
