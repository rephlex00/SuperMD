"""Sidecar entry point. Reads JSON-RPC 2.0 framed messages from stdin, dispatches
to handlers, writes responses + notifications to stdout, logs to stderr.

Run ``python -m supermd_sidecar`` to start; the SwiftUI app spawns this binary
with a piped stdin/stdout. Standalone use is supported for debugging — type
JSON requests one per line.
"""

from __future__ import annotations

import json
import logging
import sys
import threading

from supermd_sidecar.rpc import RpcServer
from supermd_sidecar.handlers import build_dispatch_table
from supermd_sidecar.state import SidecarState


class _EmitHandler(logging.Handler):
    """Mirrors log records as ``log.line`` JSON-RPC notifications so the host
    can show them in its log-tail UI. Bound lazily once the RpcServer is up."""

    def __init__(self) -> None:
        super().__init__()
        self._emit = None

    def bind(self, emit_fn) -> None:
        self._emit = emit_fn

    def emit(self, record: logging.LogRecord) -> None:
        if self._emit is None:
            return
        try:
            self._emit("log.line", {
                "level": record.levelname,
                "msg": record.getMessage(),
                "name": record.name,
            })
        except Exception:  # noqa: BLE001
            self.handleError(record)


_emit_handler = _EmitHandler()


def _configure_logging() -> None:
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [stream, _emit_handler]
    root.setLevel(logging.INFO)


def main() -> int:
    _configure_logging()
    log = logging.getLogger("sidecar")

    state = SidecarState()
    dispatch = build_dispatch_table(state)
    server = RpcServer(stdin=sys.stdin, stdout=sys.stdout, dispatch=dispatch)
    state.bind_emitter(server.emit)
    _emit_handler.bind(server.emit)

    log.info("supermd-sidecar started, awaiting requests on stdin")

    # Read loop blocks the main thread; long-running tasks dispatch to threads.
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Interrupted, shutting down")
    except Exception:  # noqa: BLE001
        log.exception("Fatal error in RPC loop")
        return 1
    finally:
        state.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
