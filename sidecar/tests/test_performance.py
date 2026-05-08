"""Performance regression tests — time-budget guards on hot paths.

These aren't trying to benchmark the engine; they're trying to catch the
class of bug where someone accidentally adds a `time.sleep` in a hot path,
or where a code path starts blocking for tens of seconds when it should be
milliseconds.

Budgets are deliberately loose (5x or 10x what we observe locally) so they
don't flake on slower CI runners, but they'd still fail if a regression
caused a 100x slowdown.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

import pytest

# Same tiny PNG used in test_handlers_convert.py
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAQAAAAYUaQ4AAAAEklEQVQI12NgYGBgYGD4DwABBgEAAGAFTwAAAABJRU5ErkJggg=="
)


# -- helpers --


def _wait_for(harness, method: str, task_id: str | None = None,
              timeout: float = 6.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for n in harness.notifications():
            if n.get("method") != method:
                continue
            if task_id and n["params"].get("task_id") != task_id:
                continue
            return n
        time.sleep(0.01)
    raise AssertionError(f"never received {method} for {task_id}")


# -- tests --


def test_ping_roundtrip_under_50ms(harness):
    """A round-trip ping through the in-memory harness should be near-instant.
    If this regresses to seconds, something is parking the read loop."""
    # Warm up the dispatch thread first.
    harness.call("system.ping")

    start = time.monotonic()
    harness.call("system.ping")
    elapsed = time.monotonic() - start

    assert elapsed < 0.05, f"ping roundtrip took {elapsed:.3f}s (>50ms budget)"


def test_100_pings_under_2s(harness):
    """Stress: 100 sequential ping/pong should still finish quickly. Catches
    accidental O(n) state lookups or busy-wait loops in the dispatch path."""
    start = time.monotonic()
    for _ in range(100):
        harness.call("system.ping")
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"100 pings took {elapsed:.2f}s (>2s budget)"


def test_convert_single_png_under_5s_with_stub_llm(harness, tmp_path, monkeypatch):
    """An end-to-end convert of one tiny PNG with a stubbed LLM should finish
    in a few hundred milliseconds. Budget set to 5s for slow CI runners."""
    from supermd import ai_utils
    monkeypatch.setattr(
        ai_utils,
        "image_to_markdown",
        lambda *a, **kw: "# stub\n",
    )
    monkeypatch.setattr(ai_utils, "validate_model_key", lambda model: None)

    src = tmp_path / "page.png"
    src.write_bytes(_TINY_PNG)
    dst = tmp_path / "out"
    dst.mkdir()

    start = time.monotonic()
    resp = harness.call("convert.file", {
        "input": str(src),
        "output": str(dst),
        "config": {"defaults": {"cooldown": 0}},
    })
    _wait_for(harness, "convert.finished", resp["result"]["task_id"], timeout=5.0)
    elapsed = time.monotonic() - start

    assert elapsed < 5.0, f"convert took {elapsed:.2f}s (>5s budget)"


def test_otp_round_trip_under_500ms(harness, stub_sncloud):
    """The OTP flow involves cross-thread coordination — make sure it's not
    accidentally pessimised with a long polling delay."""
    # Force OTP path
    stub_sncloud.__init__ = (lambda self: (
        setattr(self, "_access_token", None),
        setattr(self, "behavior", "e1760"),
        setattr(self, "listing", {}),
        setattr(self, "last_email", None),
        setattr(self, "otp_received", None),
        stub_sncloud.instances.append(self),
    ) and None)

    rid = harness.send("cloud.login", {"email": "x@y.z", "password": "pw"})

    # Wait for the otp_required event
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if [n for n in harness.notifications() if n.get("method") == "cloud.otp_required"]:
            break
        time.sleep(0.005)
    else:
        raise AssertionError("never got otp_required")

    start = time.monotonic()
    harness.call("cloud.submit_otp", {"code": "999999"})
    resp = harness.wait(rid, timeout=2.0)
    elapsed = time.monotonic() - start

    assert resp["result"]["ok"] is True
    assert elapsed < 0.5, f"OTP round-trip took {elapsed:.3f}s (>500ms budget)"


def test_directory_walk_scales_linearly(harness, tmp_path, monkeypatch):
    """Walking 50 PNGs and queuing them should be near-instant — under 2s.
    Catches regressions like an accidental quadratic file-stat loop."""
    from supermd import ai_utils
    monkeypatch.setattr(ai_utils, "image_to_markdown", lambda *a, **kw: "# x\n")
    monkeypatch.setattr(ai_utils, "validate_model_key", lambda m: None)

    src = tmp_path / "src"
    src.mkdir()
    for i in range(50):
        (src / f"p{i:03d}.png").write_bytes(_TINY_PNG)
    dst = tmp_path / "dst"
    dst.mkdir()

    start = time.monotonic()
    resp = harness.call("convert.directory", {
        "input": str(src),
        "output": str(dst),
        "config": {"defaults": {"cooldown": 0}},
    })
    enqueue_elapsed = time.monotonic() - start

    assert resp["result"]["files"] == 50
    assert enqueue_elapsed < 2.0, (
        f"queueing 50 files took {enqueue_elapsed:.2f}s (>2s budget)"
    )
