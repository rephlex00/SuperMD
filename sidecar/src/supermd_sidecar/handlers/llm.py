"""llm.* RPC methods — list models across providers, probe Ollama, validate
API keys.

API keys are stored in the macOS Keychain (via the ``keyring`` library) under
service ``com.supermd.app``. The Swift host writes them; the sidecar only
reads them so they can be exported into the env for the ``llm`` library.
"""

from __future__ import annotations

import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List

from supermd_sidecar.rpc import Handler, RpcContext, rpc_error
from supermd_sidecar.state import SidecarState

log = logging.getLogger(__name__)

PROVIDER_ENV_VAR = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

_KEYCHAIN_SERVICE = "com.supermd.app"


def _keyring():
    try:
        import keyring  # noqa: PLC0415
        return keyring
    except ImportError:
        return None


def _list_ollama_models() -> List[Dict[str, Any]]:
    """Probe a local Ollama server. Returns [] if not running."""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1.5) as resp:
            import json

            data = json.loads(resp.read().decode("utf-8"))
        return [
            {"id": m.get("name"), "size": m.get("size"), "modified": m.get("modified_at")}
            for m in data.get("models", [])
        ]
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        log.debug("Ollama probe failed: %s", e)
        return []


def _list_api_models() -> List[Dict[str, Any]]:
    """Use the ``llm`` library's plugin registry to enumerate cloud models."""
    try:
        import llm  # noqa: PLC0415
    except ImportError:
        return []

    out: List[Dict[str, Any]] = []
    for model in llm.get_models():
        # Skip Ollama models — those are handled separately.
        provider = type(model).__module__.split(".")[0]
        if "ollama" in provider:
            continue
        out.append({"id": model.model_id, "provider": provider})
    return out


def register(state: SidecarState) -> Dict[str, Handler]:
    def list_models(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "api": _list_api_models(),
            "ollama": _list_ollama_models(),
        }

    def ollama_status(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        models = _list_ollama_models()
        return {"running": bool(models) or _ollama_is_alive(), "models": models}

    def test_key(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        provider = params.get("provider")
        key = params.get("key")
        if not provider or not key:
            raise rpc_error(-32602, "provider and key are required")

        env_var = PROVIDER_ENV_VAR.get(provider)
        if env_var is None:
            raise rpc_error(-32602, f"unsupported provider: {provider}")

        # Quick liveness check: list one model and call .prompt() with a 1-token
        # ceiling. We don't want to bill the user for a real call, so we just
        # try to instantiate a model and check the auth is recognized.
        os.environ[env_var] = key
        try:
            import llm  # noqa: PLC0415

            sample_id = {
                "openai": "gpt-4o-mini",
                "anthropic": "claude-3-5-haiku-latest",
                "gemini": "gemini-2.0-flash",
            }[provider]
            llm.get_model(sample_id)
            return {"ok": True, "model": sample_id}
        except Exception as e:  # noqa: BLE001
            raise rpc_error(-32001, f"key rejected: {e}")

    def set_key(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        provider = params.get("provider")
        key = params.get("key")
        if not provider or not key:
            raise rpc_error(-32602, "provider and key are required")

        kr = _keyring()
        if kr is None:
            raise rpc_error(-32002, "keyring not available in this environment")
        kr.set_password(_KEYCHAIN_SERVICE, f"llm.{provider}", key)

        # Also export for the current process so subsequent convert calls work
        # immediately without restarting the sidecar.
        env_var = PROVIDER_ENV_VAR.get(provider)
        if env_var:
            os.environ[env_var] = key
        return {"ok": True}

    def get_key(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        provider = params.get("provider")
        kr = _keyring()
        if kr is None:
            return {"present": False}
        val = kr.get_password(_KEYCHAIN_SERVICE, f"llm.{provider}")
        return {"present": bool(val)}

    return {
        "llm.list_models": list_models,
        "llm.ollama_status": ollama_status,
        "llm.test_key": test_key,
        "llm.set_key": set_key,
        "llm.get_key": get_key,
    }


def _ollama_is_alive() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:11434/", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False
