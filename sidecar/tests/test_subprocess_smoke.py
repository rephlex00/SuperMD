"""End-to-end test that spawns the real sidecar binary as a subprocess and
talks to it over actual stdin/stdout pipes.

The in-memory `harness` fixture is great for unit tests but skips a layer of
risk: how the JSON-RPC framing behaves under real OS pipe buffering, how
stdout flushing works in production, whether import order matters at startup.
This test catches all of that.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def sidecar_proc(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        str(REPO_ROOT / "sidecar/src") + os.pathsep +
        str(REPO_ROOT / "src") + os.pathsep +
        env.get("PYTHONPATH", "")
    )
    env["SUPERMD_CONFIG_DIR"] = str(tmp_path / "config")
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["XDG_DATA_HOME"] = str(tmp_path / "data")
    env["XDG_CACHE_HOME"] = str(tmp_path / "cache")
    # Force unbuffered to keep the test snappy (the sidecar already flushes
    # explicitly, but Python may still buffer stdin/stderr).
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "-m", "supermd_sidecar"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        bufsize=1,
    )

    # Drain stderr in the background so it can't fill up the pipe and block.
    stderr_lines: list[str] = []

    def drain():
        for line in proc.stderr:  # type: ignore[union-attr]
            stderr_lines.append(line.rstrip())

    t = threading.Thread(target=drain, daemon=True)
    t.start()

    yield proc, stderr_lines

    if proc.poll() is None:
        try:
            proc.stdin.write('{"jsonrpc":"2.0","id":99,"method":"system.shutdown"}\n')
            proc.stdin.flush()
            proc.wait(timeout=2)
        except Exception:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


def _send_recv(proc, request: dict, timeout: float = 3.0) -> dict:
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.01)
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Skip server-initiated notifications (no id), wait for our response
        if obj.get("id") == request.get("id"):
            return obj
    raise AssertionError(
        f"timed out waiting for response to id={request.get('id')}"
    )


def test_subprocess_starts_and_responds_to_ping(sidecar_proc):
    proc, _ = sidecar_proc
    resp = _send_recv(proc, {"jsonrpc": "2.0", "id": 1, "method": "system.ping"})
    assert resp["result"]["pong"] is True
    assert "version" in resp["result"]
    assert "pid" in resp["result"]
    # The PID in the response should match the actual subprocess PID.
    assert resp["result"]["pid"] == proc.pid


def test_subprocess_handles_unknown_method(sidecar_proc):
    proc, _ = sidecar_proc
    resp = _send_recv(proc, {"jsonrpc": "2.0", "id": 2, "method": "does.not.exist"})
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_subprocess_survives_malformed_json_and_then_responds(sidecar_proc):
    """A garbage line on stdin must not crash the loop."""
    proc, _ = sidecar_proc
    proc.stdin.write("this is not json\n")
    proc.stdin.flush()

    # Now a real request should still get a real response.
    resp = _send_recv(proc, {"jsonrpc": "2.0", "id": 3, "method": "system.ping"})
    assert resp["result"]["pong"] is True


def test_subprocess_round_trips_config_paths(sidecar_proc, tmp_path):
    """The sidecar should report config paths under our test-controlled
    XDG_CONFIG_HOME, proving env propagation through the subprocess works."""
    proc, _ = sidecar_proc
    resp = _send_recv(proc, {"jsonrpc": "2.0", "id": 4, "method": "system.config_path"})
    r = resp["result"]
    assert str(tmp_path) in r["config_path"]


def test_subprocess_clean_shutdown_via_rpc(sidecar_proc):
    """system.shutdown should make the process exit cleanly with code 0."""
    proc, _ = sidecar_proc
    resp = _send_recv(proc, {"jsonrpc": "2.0", "id": 5, "method": "system.shutdown"})
    assert resp["result"]["ok"] is True
    proc.wait(timeout=3)
    assert proc.returncode == 0
