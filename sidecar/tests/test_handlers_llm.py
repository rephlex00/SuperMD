"""llm.* handler tests — model listing, ollama probe, key validation.

We mock both the `llm` library and Ollama's HTTP endpoint so the tests don't
require any real model or running daemon.
"""

from __future__ import annotations

import io
import urllib.request
from unittest.mock import patch

import pytest


def test_list_models_with_no_providers_returns_empty(harness, monkeypatch):
    # Patch out the llm library so it acts as if no models are registered.
    import sys
    import types
    fake = types.ModuleType("llm")
    fake.get_models = lambda: []
    monkeypatch.setitem(sys.modules, "llm", fake)

    # And ensure Ollama probe fails
    def boom(*a, **kw):
        raise OSError("connection refused")
    monkeypatch.setattr(urllib.request, "urlopen", boom)

    resp = harness.call("llm.list_models")
    r = resp["result"]
    assert r["api"] == []
    assert r["ollama"] == []


def test_list_models_returns_ollama_models(harness, monkeypatch):
    body = b'{"models": [{"name": "qwen2.5-vl:7b", "size": 4500000000, "modified_at": "2026-01-01"}]}'

    class FakeResp:
        status = 200
        def __init__(self): self._b = body
        def read(self): return self._b
        def __enter__(self): return self
        def __exit__(self, *a): pass

    def fake_urlopen(url, timeout=None):
        if "tags" in url:
            return FakeResp()
        raise OSError("nope")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    # Suppress the api side for this test
    import sys, types
    fake = types.ModuleType("llm")
    fake.get_models = lambda: []
    monkeypatch.setitem(sys.modules, "llm", fake)

    resp = harness.call("llm.list_models")
    r = resp["result"]
    assert any(m["id"] == "qwen2.5-vl:7b" for m in r["ollama"])


def test_test_key_with_unknown_provider_errors(harness):
    resp = harness.call("llm.test_key", {"provider": "fake-co", "key": "x"})
    assert "error" in resp
    assert resp["error"]["code"] == -32602


def test_set_key_persists_via_keyring(harness, monkeypatch):
    """set_key should write to keyring and export the env var."""
    import os
    import sys
    import types

    set_calls = []
    fake_keyring = types.ModuleType("keyring")
    fake_keyring.set_password = lambda service, key, value: set_calls.append((service, key, value))
    fake_keyring.get_password = lambda service, key: "preexisting"
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)

    resp = harness.call("llm.set_key", {"provider": "openai", "key": "sk-xxx"})
    assert resp["result"]["ok"] is True
    assert set_calls == [("com.supermd.app", "llm.openai", "sk-xxx")]
    assert os.environ.get("OPENAI_API_KEY") == "sk-xxx"


def test_ollama_status_returns_running_false_when_unreachable(harness, monkeypatch):
    def boom(*a, **kw):
        raise OSError("nope")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    resp = harness.call("llm.ollama_status")
    assert resp["result"]["running"] is False
    assert resp["result"]["models"] == []
