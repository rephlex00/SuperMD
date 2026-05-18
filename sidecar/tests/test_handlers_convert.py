"""convert.* handler tests.

We use a tiny PNG fixture (the simplest extractor — passthrough) and stub the
LLM call so the test is self-contained and runs in milliseconds.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import pytest

# A 4x4 black PNG, base64-encoded — just enough to be a valid input.
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAQAAAAYUaQ4AAAAEklEQVQI12NgYGBgYGD4DwABBgEAAGAFTwAAAABJRU5ErkJggg=="
)


@pytest.fixture
def tiny_png(tmp_path):
    p = tmp_path / "page.png"
    p.write_bytes(_TINY_PNG)
    return p


@pytest.fixture
def stub_llm(monkeypatch):
    """Make the engine's ai_utils.image_to_markdown return a fixed string
    instead of actually calling an LLM. converter.py imports the function
    by name (`from supermd.ai_utils import image_to_markdown`), so we have
    to patch both the source module *and* the local binding the converter
    captured at import time — otherwise tests that ran earlier in the
    process can leave a stale reference and we hit the real API."""
    from supermd import ai_utils, converter
    stub = lambda image_path, context, model, prompt, ctx_dict: "# Hello from stub\n"
    monkeypatch.setattr(ai_utils, "image_to_markdown", stub)
    monkeypatch.setattr(converter, "image_to_markdown", stub)
    monkeypatch.setattr(ai_utils, "validate_model_key", lambda model: None)


def test_convert_file_emits_started_and_finished(harness, tiny_png, tmp_path, stub_llm):
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    resp = harness.call("convert.file", {
        "input": str(tiny_png),
        "output": str(output_dir),
        "config": {"model": "gpt-4o-mini", "defaults": {"cooldown": 0}},
    })
    task_id = resp["result"]["task_id"]
    assert task_id.startswith("conv-")

    # Poll for the convert.finished notification
    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline:
        notes = harness.notifications()
        finished = [n for n in notes
                    if n.get("method") == "convert.finished"
                    and n["params"].get("task_id") == task_id]
        if finished:
            break
        time.sleep(0.05)
    else:
        notes = harness.notifications()
        raise AssertionError(f"convert never finished. events: {notes}")

    # Markdown file should now exist
    written = list(output_dir.rglob("*.md"))
    assert written, "no markdown was written"
    assert "Hello from stub" in written[0].read_text()


def test_convert_missing_input_errors(harness, tmp_path):
    resp = harness.call("convert.file", {
        "input": str(tmp_path / "nope.png"),
        "output": str(tmp_path),
    })
    assert "error" in resp
    assert resp["error"]["code"] == -32020


def test_convert_directory_queues_one_task_per_file(harness, tmp_path, stub_llm):
    src = tmp_path / "src"; src.mkdir()
    dst = tmp_path / "dst"; dst.mkdir()
    (src / "a.png").write_bytes(_TINY_PNG)
    (src / "b.png").write_bytes(_TINY_PNG)
    (src / "ignore.txt").write_text("hi")  # not supported

    resp = harness.call("convert.directory", {
        "input": str(src),
        "output": str(dst),
        "config": {"defaults": {"cooldown": 0}},
    })
    assert resp["result"]["files"] == 2


def test_convert_unchanged_input_skips(harness, tmp_path, stub_llm):
    """Second invocation against the same input should emit
    convert.skipped(reason=input_unchanged)."""
    src = tmp_path / "src"; src.mkdir()
    p = src / "a.png"; p.write_bytes(_TINY_PNG)
    dst = tmp_path / "dst"; dst.mkdir()

    cfg = {"defaults": {"cooldown": 0}}
    harness.call("convert.file", {"input": str(p), "output": str(dst), "config": cfg})

    # Wait for first one to finish
    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline:
        if [n for n in harness.notifications() if n.get("method") == "convert.finished"]:
            break
        time.sleep(0.05)

    # Second run
    resp = harness.call("convert.file", {"input": str(p), "output": str(dst), "config": cfg})
    task_id = resp["result"]["task_id"]
    deadline = time.monotonic() + 4.0
    while time.monotonic() < deadline:
        skipped = [n for n in harness.notifications()
                   if n.get("method") == "convert.skipped"
                   and n["params"].get("task_id") == task_id]
        if skipped:
            assert skipped[0]["params"]["reason"] == "input_unchanged"
            break
        time.sleep(0.05)
    else:
        raise AssertionError("skip notification never arrived")
