"""End-to-end tests against the real supermd engine, including the
supernotelib parser.

These tests require a `sample.note` fixture in `sidecar/tests/fixtures/`.
If it's missing, every test in this module is skipped — see
`fixtures/README.md` for instructions.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"
NOTE_FIXTURE = FIXTURE_DIR / "sample.note"
SPD_FIXTURE = FIXTURE_DIR / "sample.spd"


@pytest.fixture
def note_file():
    if not NOTE_FIXTURE.exists():
        pytest.skip(
            f"Real .note fixture not present at {NOTE_FIXTURE}. "
            "See sidecar/tests/fixtures/README.md to enable these tests."
        )
    return NOTE_FIXTURE


@pytest.fixture
def spd_file():
    if not SPD_FIXTURE.exists():
        pytest.skip(f"No .spd fixture at {SPD_FIXTURE}")
    return SPD_FIXTURE


def _wait_for_notification(harness, method: str, task_id: str | None = None,
                           timeout: float = 10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for n in harness.notifications():
            if n.get("method") != method:
                continue
            if task_id and n["params"].get("task_id") != task_id:
                continue
            return n
        time.sleep(0.05)
    raise AssertionError(
        f"never received {method!r} (task_id={task_id!r}); "
        f"got: {[n['method'] for n in harness.notifications()]}"
    )


def _stub_llm(monkeypatch):
    """Replace LLM calls everywhere they're imported. converter.py does
    `from supermd.ai_utils import image_to_markdown` at module-load time so
    patching `ai_utils.image_to_markdown` alone isn't enough — the converter
    has already bound its own reference."""
    from supermd import ai_utils, converter
    stub = lambda image_path, context, model, prompt, ctx_dict: "# stub page\n"
    monkeypatch.setattr(ai_utils, "image_to_markdown", stub)
    monkeypatch.setattr(converter, "image_to_markdown", stub)
    monkeypatch.setattr(ai_utils, "validate_model_key", lambda model: None)


def test_convert_real_note_file_produces_markdown(harness, tmp_path,
                                                  note_file, monkeypatch):
    """Drop a real .note in, get Markdown out. Stubs the LLM so we exercise
    the parser/extractor path but not the network."""
    _stub_llm(monkeypatch)

    output_dir = tmp_path / "out"
    output_dir.mkdir()

    resp = harness.call("convert.file", {
        "input": str(note_file),
        "output": str(output_dir),
        "config": {"defaults": {"cooldown": 0}},
    })
    task_id = resp["result"]["task_id"]
    _wait_for_notification(harness, "convert.finished", task_id)

    markdowns = list(output_dir.rglob("*.md"))
    assert markdowns, "no .md emitted"
    text = markdowns[0].read_text()
    assert "stub page" in text


def test_skip_unchanged_real_note(harness, tmp_path, note_file, monkeypatch):
    """Second pass over the same .note should be skipped via the metadata DB."""
    _stub_llm(monkeypatch)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    cfg = {"defaults": {"cooldown": 0}}

    r1 = harness.call("convert.file",
                      {"input": str(note_file), "output": str(output_dir), "config": cfg})
    _wait_for_notification(harness, "convert.finished", r1["result"]["task_id"])

    r2 = harness.call("convert.file",
                      {"input": str(note_file), "output": str(output_dir), "config": cfg})
    skip = _wait_for_notification(harness, "convert.skipped", r2["result"]["task_id"])
    assert skip["params"]["reason"] == "input_unchanged"
