"""config.* handler tests — read, write, validate."""

from __future__ import annotations

import textwrap


def test_read_when_no_file_returns_defaults(harness):
    resp = harness.call("config.read")
    r = resp["result"]
    assert r["exists"] is False
    assert r["yaml"] == ""
    # Defaults must include the engine's known keys
    assert "model" in r["data"]
    assert "template" in r["data"]


def test_write_then_read_round_trips(harness):
    yaml_text = textwrap.dedent("""\
        model: gpt-4o-mini
        prompt: |
          Test prompt
        template: "{{llm_output}}"
        defaults:
          force: false
          progress: true
          level: INFO
          cooldown: 5.0
        jobs: []
    """)
    resp = harness.call("config.write", {"yaml": yaml_text})
    assert resp["result"]["ok"] is True

    resp2 = harness.call("config.read")
    assert resp2["result"]["exists"] is True
    assert "Test prompt" in resp2["result"]["yaml"]


def test_write_invalid_yaml_returns_error(harness):
    resp = harness.call("config.write", {"yaml": "this: is: not: valid: yaml: ::"})
    assert "error" in resp
    assert resp["error"]["code"] == -32031


def test_write_valid_yaml_but_invalid_schema_returns_error(harness):
    # ``model`` must be a string, not a dict
    resp = harness.call("config.write", {"yaml": "model:\n  oops: 1\n"})
    assert "error" in resp
    assert resp["error"]["code"] == -32031


def test_defaults_endpoint_returns_serialisable_yaml(harness):
    resp = harness.call("config.defaults")
    r = resp["result"]
    assert "model" in r["data"]
    assert "model" in r["yaml"]
