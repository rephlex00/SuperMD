"""system.* RPC methods — ping, version, shutdown, paths."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict

from supermd_sidecar import __version__
from supermd_sidecar.rpc import Handler, RpcContext, rpc_error
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

    def set_log_level(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        level = (params.get("level") or "").upper()
        levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in levels:
            raise rpc_error(-32602, f"unsupported level: {level!r}; expected one of {sorted(levels)}")
        logging.getLogger().setLevel(getattr(logging, level))
        return {"ok": True, "level": level}

    return {
        "system.ping": ping,
        "system.shutdown": shutdown,
        "system.config_path": config_path,
        "system.set_log_level": set_log_level,
    }
