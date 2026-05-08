"""obsidian.* handler tests — vault discovery, URI launching."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_list_vaults_returns_registered(harness, fake_obsidian_registry):
    resp = harness.call("obsidian.list_vaults")
    vaults = resp["result"]["vaults"]
    names = sorted(v["name"] for v in vaults)
    assert names == ["DoesNotExist", "VaultA", "VaultB"]
    # `exists` should reflect filesystem reality
    by_name = {v["name"]: v for v in vaults}
    assert by_name["VaultA"]["exists"] is True
    assert by_name["DoesNotExist"]["exists"] is False


def test_list_vaults_with_no_registry_returns_empty(harness, monkeypatch, tmp_path):
    from supermd_sidecar.handlers import obsidian as ob_mod
    monkeypatch.setattr(ob_mod, "OBSIDIAN_REGISTRY", tmp_path / "missing.json")
    resp = harness.call("obsidian.list_vaults")
    assert resp["result"]["vaults"] == []


def test_open_note_invokes_open_with_uri(harness, fake_obsidian_registry, monkeypatch):
    calls = []

    def fake_run(args, **kw):
        calls.append(args)
        class R: returncode = 0
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    resp = harness.call("obsidian.open_note",
                        {"vault": "VaultA", "file": "Notes/Today.md"})
    assert resp["result"]["ok"] is True
    assert calls and calls[0][0] == "open"
    assert calls[0][1].startswith("obsidian://open?")
    assert "VaultA" in calls[0][1]
    assert "Notes" in calls[0][1]


def test_open_note_requires_vault_and_file(harness):
    resp = harness.call("obsidian.open_note", {"vault": "X"})
    assert "error" in resp
    assert resp["error"]["code"] == -32602
