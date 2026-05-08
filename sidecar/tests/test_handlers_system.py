"""system.* handler tests."""

from __future__ import annotations


def test_config_path_returns_paths_inside_config_dir(harness):
    resp = harness.call("system.config_path")
    r = resp["result"]
    assert r["config_path"].endswith("config.yaml")
    assert "log_dir" in r
    assert "metadata_db" in r


def test_ping_includes_python_version(harness):
    resp = harness.call("system.ping")
    r = resp["result"]
    assert "python" in r
    assert r["python"].count(".") >= 1
