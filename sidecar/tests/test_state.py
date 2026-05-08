"""SidecarState — OTP request/submit threading."""

from __future__ import annotations

import threading
import time

from supermd_sidecar.state import SidecarState


def test_request_otp_blocks_until_submit():
    state = SidecarState()
    state.bind_emitter(lambda *a: None)

    received = []

    def waiter():
        received.append(state.request_otp())

    t = threading.Thread(target=waiter, daemon=True)
    t.start()

    time.sleep(0.05)  # let the waiter park
    assert received == []  # still blocked

    state.submit_otp("999999")
    t.join(timeout=1.0)
    assert received == ["999999"]


def test_submit_otp_with_no_pending_request_raises():
    state = SidecarState()
    try:
        state.submit_otp("000000")
    except RuntimeError as e:
        assert "no otp" in str(e).lower()
    else:
        raise AssertionError("expected RuntimeError")
