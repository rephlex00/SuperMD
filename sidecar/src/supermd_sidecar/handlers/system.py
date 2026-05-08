"""system.* RPC methods — ping, version, shutdown, paths."""

from __future__ import annotations

import os
import sys
from typing import Any, Dict

from supermd_sidecar import __version__
from supermd_sidecar.rpc import Handler, RpcContext
from supermd_sidecar.state import SidecarState


def register(state: SidecarState) -> Dict[str, Handler]:
    def ping(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "pong": True,
            "version": __version__,
            "python": sys.version.split()[0],
            "pid": os.getpid(),
        }

    def shutdown(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        # Schedule a graceful exit after the response is flushed.
        import threading
        import time

        def _exit():
            time.sleep(0.05)
            os._exit(0)

        threading.Thread(target=_exit, daemon=True).start()
        return {"ok": True}

    def config_path(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "config_path": str(state.config_path),
            "config_dir": str(state.config_dir),
            "log_dir": str(state.log_dir),
            "metadata_db": str(state.metadata_db),
        }

    return {
        "system.ping": ping,
        "system.shutdown": shutdown,
        "system.config_path": config_path,
    }
