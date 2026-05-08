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


def _configure_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def main() -> int:
    _configure_logging()
    log = logging.getLogger("sidecar")

    state = SidecarState()
    dispatch = build_dispatch_table(state)
    server = RpcServer(stdin=sys.stdin, stdout=sys.stdout, dispatch=dispatch)
    state.bind_emitter(server.emit)

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
