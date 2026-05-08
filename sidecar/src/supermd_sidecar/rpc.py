"""Minimal JSON-RPC 2.0 server over line-framed stdio.

We don't need batching, named params, or the full spec — just request/response
plus server-initiated notifications (for streaming progress to the host).
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import traceback
from dataclasses import dataclass
from typing import Any, Callable, Dict, IO

log = logging.getLogger(__name__)

Handler = Callable[["RpcContext", Dict[str, Any]], Dict[str, Any]]


@dataclass
class RpcContext:
    """Passed to every handler. ``emit`` lets a handler push a notification
    back to the host independently of its return value (e.g. progress updates
    during a long-running task).
    """

    request_id: Any
    emit: Callable[[str, Dict[str, Any]], None]


class RpcServer:
    def __init__(
        self,
        stdin: IO[str],
        stdout: IO[str],
        dispatch: Dict[str, Handler],
    ):
        self._stdin = stdin
        self._stdout = stdout
        self._dispatch = dispatch
        self._write_lock = threading.Lock()
        self._stop = threading.Event()

    def emit(self, method: str, params: Dict[str, Any]) -> None:
        """Send a server-initiated notification (no id)."""
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _send(self, payload: Dict[str, Any]) -> None:
        line = json.dumps(payload, separators=(",", ":"), default=str)
        with self._write_lock:
            self._stdout.write(line + "\n")
            self._stdout.flush()

    def _send_error(self, request_id: Any, code: int, message: str, data: Any = None):
        err: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        self._send({"jsonrpc": "2.0", "id": request_id, "error": err})

    def _handle(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError as e:
            self._send_error(None, -32700, f"parse error: {e}")
            return

        if not isinstance(msg, dict):
            self._send_error(None, -32600, "request must be a JSON object")
            return

        request_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}

        if not isinstance(method, str):
            self._send_error(request_id, -32600, "missing or invalid 'method'")
            return

        handler = self._dispatch.get(method)
        if handler is None:
            self._send_error(request_id, -32601, f"unknown method: {method}")
            return

        # Run the handler in a worker thread so a slow handler doesn't block
        # the read loop (and other RPCs can still come in concurrently).
        threading.Thread(
            target=self._invoke,
            args=(handler, request_id, params),
            name=f"rpc:{method}",
            daemon=True,
        ).start()

    def _invoke(self, handler: Handler, request_id: Any, params: Dict[str, Any]) -> None:
        ctx = RpcContext(request_id=request_id, emit=self.emit)
        try:
            result = handler(ctx, params)
        except _RpcError as e:
            self._send_error(request_id, e.code, e.message, e.data)
            return
        except Exception as e:  # noqa: BLE001
            log.exception("Handler raised")
            self._send_error(
                request_id,
                -32000,
                f"{type(e).__name__}: {e}",
                {"traceback": traceback.format_exc()},
            )
            return

        if request_id is None:
            return  # notification: no response expected
        self._send({"jsonrpc": "2.0", "id": request_id, "result": result})

    def serve_forever(self) -> None:
        for line in self._stdin:
            line = line.strip()
            if not line:
                continue
            if self._stop.is_set():
                break
            self._handle(line)


class _RpcError(Exception):
    """Raise from a handler to send a structured JSON-RPC error response."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def rpc_error(code: int, message: str, data: Any = None) -> _RpcError:
    return _RpcError(code, message, data)
