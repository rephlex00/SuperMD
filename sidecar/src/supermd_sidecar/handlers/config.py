"""config.* RPC methods — read and write the on-disk YAML config that the
engine and the SwiftUI app share.
"""

from __future__ import annotations

import io
from typing import Any, Dict

from ruamel.yaml import YAML

from supermd_sidecar.rpc import Handler, RpcContext, rpc_error
from supermd_sidecar.state import SidecarState

_yaml = YAML()
_yaml.preserve_quotes = True


def _default_config_dict() -> Dict[str, Any]:
    """Build the default config the engine would use, as a serialisable dict."""
    from supermd.config import SuperMDConfig

    return SuperMDConfig().model_dump()


def register(state: SidecarState) -> Dict[str, Handler]:
    def read(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        path = state.config_path
        if not path.exists():
            return {"yaml": "", "data": _default_config_dict(), "exists": False}
        text = path.read_text(encoding="utf-8")
        try:
            data = _yaml.load(text) or {}
        except Exception as e:  # noqa: BLE001
            raise rpc_error(-32030, f"failed to parse config: {e}")
        return {"yaml": text, "data": data, "exists": True}

    def write(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        yaml_text = params.get("yaml")
        if yaml_text is None:
            raise rpc_error(-32602, "yaml is required")
        # Validate by attempting to load through the engine model
        try:
            from supermd.config import SuperMDConfig

            data = _yaml.load(yaml_text) or {}
            SuperMDConfig(**data)
        except Exception as e:  # noqa: BLE001
            raise rpc_error(-32031, f"invalid config: {e}")

        state.config_path.parent.mkdir(parents=True, exist_ok=True)
        state.config_path.write_text(yaml_text, encoding="utf-8")
        return {"ok": True, "path": str(state.config_path)}

    def defaults(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        # Render defaults as YAML too, so the host can prefill the editor.
        buf = io.StringIO()
        _yaml.dump(_default_config_dict(), buf)
        return {"data": _default_config_dict(), "yaml": buf.getvalue()}

    return {
        "config.read": read,
        "config.write": write,
        "config.defaults": defaults,
    }
