"""obsidian.* RPC methods — vault discovery, note opening, optional headless
Obsidian process management.

The Obsidian app maintains its vault registry at
``~/Library/Application Support/obsidian/obsidian.json`` on macOS. We read it
to enumerate vaults; the file is JSON of the form:

    { "vaults": { "<id>": { "path": "/Users/.../Vault", "ts": ..., "open": true } } }
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import signal
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List

from supermd_sidecar.rpc import Handler, RpcContext, rpc_error
from supermd_sidecar.state import SidecarState

log = logging.getLogger(__name__)

OBSIDIAN_REGISTRY = Path.home() / "Library/Application Support/obsidian/obsidian.json"


def _list_vaults() -> List[Dict[str, Any]]:
    if not OBSIDIAN_REGISTRY.exists():
        return []
    try:
        data = json.loads(OBSIDIAN_REGISTRY.read_text())
    except (OSError, json.JSONDecodeError) as e:
        log.warning("could not read Obsidian registry: %s", e)
        return []

    vaults = []
    for vault_id, info in (data.get("vaults") or {}).items():
        path = info.get("path")
        if not path:
            continue
        vaults.append(
            {
                "id": vault_id,
                "name": Path(path).name,
                "path": path,
                "open": bool(info.get("open")),
                "exists": Path(path).is_dir(),
            }
        )
    return vaults


def register(state: SidecarState) -> Dict[str, Handler]:
    headless_proc: Dict[str, subprocess.Popen] = {}

    def list_vaults(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"vaults": _list_vaults()}

    def open_note(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        vault = params.get("vault")
        file = params.get("file")
        if not vault or not file:
            raise rpc_error(-32602, "vault and file are required")

        # obsidian://open?vault=<name>&file=<rel-path>
        uri = (
            "obsidian://open?vault="
            + urllib.parse.quote(vault, safe="")
            + "&file="
            + urllib.parse.quote(file, safe="")
        )
        subprocess.run(["open", uri], check=False)
        return {"ok": True, "uri": uri}

    def start_headless(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        vault_path = params.get("vault_path")
        if not vault_path or not Path(vault_path).is_dir():
            raise rpc_error(-32602, "vault_path must point to an existing directory")

        if "obsidian" in headless_proc and headless_proc["obsidian"].poll() is None:
            return {"ok": True, "pid": headless_proc["obsidian"].pid, "already_running": True}

        # We don't bundle Obsidian; we use the user's installation.
        # Path: /Applications/Obsidian.app/Contents/MacOS/Obsidian
        binary = Path("/Applications/Obsidian.app/Contents/MacOS/Obsidian")
        if not binary.exists():
            raise rpc_error(-32003, "Obsidian.app not found in /Applications")

        # --background suppresses the dock icon on macOS via LSUIElement at the
        # process level. Real "headless" Obsidian needs the obsidian-headless
        # CLI fork; a vanilla install can only run minimised in the dock.
        proc = subprocess.Popen(
            [str(binary), f"--vault={vault_path}", "--background"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        headless_proc["obsidian"] = proc
        return {"ok": True, "pid": proc.pid}

    def stop_headless(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        proc = headless_proc.get("obsidian")
        if proc and proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        headless_proc.pop("obsidian", None)
        return {"ok": True}

    return {
        "obsidian.list_vaults": list_vaults,
        "obsidian.open_note": open_note,
        "obsidian.start_headless": start_headless,
        "obsidian.stop_headless": stop_headless,
    }
