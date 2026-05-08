"""Shared fixtures for sidecar tests.

The tests don't spawn an actual subprocess — they wire the RPC server's
stdin/stdout to in-memory streams so we can drive it with synthetic JSON
lines and assert on the responses. This keeps tests fast and deterministic.
"""

from __future__ import annotations

import io
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

import pytest

from supermd_sidecar.handlers import build_dispatch_table
from supermd_sidecar.rpc import RpcServer
from supermd_sidecar.state import SidecarState


@dataclass
class HarnessIO:
    """Stand-in for stdin/stdout that lets the test thread push lines in and
    read responses out."""

    in_queue: List[str]
    out_lines: List[str]
    out_lock: threading.Lock
    out_cond: threading.Condition
    closed: threading.Event

    def stdin(self):
        return _QueueReader(self.in_queue, self.closed)

    def stdout(self):
        return _ListWriter(self.out_lines, self.out_lock, self.out_cond)


class _QueueReader:
    def __init__(self, queue: List[str], closed: threading.Event):
        self._queue = queue
        self._closed = closed

    def __iter__(self):
        while not self._closed.is_set():
            if not self._queue:
                time.sleep(0.01)
                continue
            yield self._queue.pop(0)


class _ListWriter:
    def __init__(self, lines: List[str], lock: threading.Lock,
                 cond: threading.Condition):
        self._lines = lines
        self._lock = lock
        self._cond = cond

    def write(self, s: str) -> None:
        if not s.endswith("\n"):
            return
        with self._cond:
            self._lines.append(s.strip())
            self._cond.notify_all()

    def flush(self) -> None:
        pass


@pytest.fixture
def harness(tmp_path, monkeypatch):
    """A running RPC server with mocked stdio. Yields an object you can call
    .send(method, params) on and that exposes .responses and .notifications.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    state = SidecarState()
    state.config_dir = tmp_path / "config"
    state.config_dir.mkdir(exist_ok=True)
    state.config_path = state.config_dir / "config.yaml"
    state.log_dir = tmp_path / "logs"
    state.log_dir.mkdir(exist_ok=True)
    state.metadata_db = state.config_dir / "metadata.sqlite"

    in_queue: List[str] = []
    out_lines: List[str] = []
    lock = threading.Lock()
    cond = threading.Condition(lock)
    closed = threading.Event()
    io_pair = HarnessIO(in_queue, out_lines, lock, cond, closed)

    dispatch = build_dispatch_table(state)
    server = RpcServer(stdin=io_pair.stdin(), stdout=io_pair.stdout(), dispatch=dispatch)
    state.bind_emitter(server.emit)

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    next_id = [0]

    def send(method: str, params: Dict[str, Any] | None = None,
             notify: bool = False) -> int | None:
        if notify:
            in_queue.append(json.dumps({
                "jsonrpc": "2.0", "method": method, "params": params or {}
            }) + "\n")
            return None
        next_id[0] += 1
        rid = next_id[0]
        in_queue.append(json.dumps({
            "jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}
        }) + "\n")
        return rid

    def wait_for_response(rid: int, timeout: float = 3.0) -> Dict[str, Any]:
        deadline = time.monotonic() + timeout
        with cond:
            while True:
                for line in out_lines:
                    obj = json.loads(line)
                    if obj.get("id") == rid:
                        return obj
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError(
                        f"timed out waiting for response id={rid}; got: {out_lines}"
                    )
                cond.wait(timeout=remaining)

    def notifications() -> List[Dict[str, Any]]:
        with lock:
            return [json.loads(l) for l in out_lines if "id" not in json.loads(l)]

    class Harness:
        def __init__(self):
            self.state = state
            self.send = send
            self.wait = wait_for_response
            self.responses = lambda: [json.loads(l) for l in out_lines if "id" in json.loads(l)]
            self.notifications = notifications
            self.lines = out_lines

        def call(self, method: str, params: Dict[str, Any] | None = None,
                 timeout: float = 3.0) -> Dict[str, Any]:
            rid = send(method, params)
            return wait_for_response(rid, timeout=timeout)

    yield Harness()

    closed.set()
    in_queue.append("")  # nudge the reader to wake


@pytest.fixture
def fake_obsidian_registry(tmp_path, monkeypatch):
    """Override the OBSIDIAN_REGISTRY path with a tmp file containing fake
    vault entries. Returns the list of vaults that were written."""
    from supermd_sidecar.handlers import obsidian as ob_mod

    vault_a = tmp_path / "VaultA"
    vault_a.mkdir()
    vault_b = tmp_path / "VaultB"
    vault_b.mkdir()

    registry = tmp_path / "obsidian.json"
    registry.write_text(json.dumps({
        "vaults": {
            "abc123": {"path": str(vault_a), "ts": 1, "open": True},
            "def456": {"path": str(vault_b), "ts": 2, "open": False},
            "ghost":  {"path": str(tmp_path / "DoesNotExist"), "ts": 3},
        }
    }))
    monkeypatch.setattr(ob_mod, "OBSIDIAN_REGISTRY", registry)
    return [vault_a, vault_b]


@pytest.fixture
def stub_sncloud(monkeypatch):
    """Replaces the sncloud package with a fake that lets us drive the OTP
    flow synchronously."""
    import sys
    import types

    fake = types.ModuleType("sncloud")
    fake_models = types.ModuleType("sncloud.models")
    fake_exc = types.ModuleType("sncloud.exceptions")

    class AuthenticationError(Exception):
        pass

    class Directory:
        def __init__(self, file_name): self.file_name = file_name
    class File:
        def __init__(self, file_name): self.file_name = file_name

    class SNClient:
        instances: list["SNClient"] = []
        def __init__(self):
            self._access_token = None
            self.behavior = "ok"
            self.listing: dict[str, list] = {}
            self.last_email: str | None = None
            self.otp_received: str | None = None
            SNClient.instances.append(self)
        def login(self, email, password):
            self.last_email = email
            if self.behavior == "ok":
                self._access_token = "TOKEN-OK"
                return
            if self.behavior == "e1760":
                raise AuthenticationError("__E1760__:1234567890")
            raise AuthenticationError(f"bad: {self.behavior}")
        def send_verification_code(self, email, ts):
            return "VALID-KEY"
        def verify_otp(self, email, code, key, ts):
            self.otp_received = code
            if code == "REJECT":
                raise AuthenticationError("bad code")
            self._access_token = "TOKEN-AFTER-OTP"
            return "TOKEN-AFTER-OTP"
        def ls(self, path):
            return self.listing.get(path, [])
        def get(self, remote, dest):
            from pathlib import Path as _P
            name = remote.rsplit("/", 1)[-1]
            (_P(dest) / name).write_bytes(b"hello")

    fake.SNClient = SNClient
    fake_models.Directory = Directory
    fake_models.File = File
    fake_exc.AuthenticationError = AuthenticationError

    monkeypatch.setitem(sys.modules, "sncloud", fake)
    monkeypatch.setitem(sys.modules, "sncloud.models", fake_models)
    monkeypatch.setitem(sys.modules, "sncloud.exceptions", fake_exc)
    return SNClient
