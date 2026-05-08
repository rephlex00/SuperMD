"""cloud.* handler tests — login (happy path, OTP path), sync, logout."""

from __future__ import annotations

import json
import time

import pytest


def test_login_happy_path(harness, stub_sncloud):
    resp = harness.call("cloud.login", {"email": "a@b.c", "password": "pw"})
    assert resp["result"]["ok"] is True
    assert resp["result"]["token"] == "TOKEN-OK"
    assert stub_sncloud.instances[-1].last_email == "a@b.c"


def test_login_with_otp_completes_via_submit(harness, stub_sncloud):
    """Drive the full E1760 flow:
       1. cloud.login is sent and blocks on the OTP request
       2. The host receives a cloud.otp_required notification
       3. We post cloud.submit_otp
       4. The original login resolves with the new token
    """
    # Pre-configure the stub to require OTP
    # The stub's behavior is set per-instance, so we must set it after the
    # client is constructed by the handler. To do that, we patch the
    # __init__ via class default:
    class B(stub_sncloud):
        pass
    stub_sncloud.__init__ = (lambda self: (
        setattr(self, "_access_token", None),
        setattr(self, "behavior", "e1760"),
        setattr(self, "listing", {}),
        setattr(self, "last_email", None),
        setattr(self, "otp_received", None),
        stub_sncloud.instances.append(self),
    ) and None)

    # Send login (will block in handler)
    rid = harness.send("cloud.login", {"email": "x@y.z", "password": "pw"})

    # Wait for the otp_required notification
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        notes = [n for n in harness.notifications() if n.get("method") == "cloud.otp_required"]
        if notes:
            assert notes[-1]["params"]["email"] == "x@y.z"
            break
        time.sleep(0.02)
    else:
        raise AssertionError("never received cloud.otp_required")

    # Submit the OTP
    sub = harness.call("cloud.submit_otp", {"code": "123456"})
    assert sub["result"]["ok"] is True

    # Now the original login should resolve
    resp = harness.wait(rid, timeout=3.0)
    assert resp["result"]["ok"] is True
    assert resp["result"]["token"] == "TOKEN-AFTER-OTP"

    # And the host should have received a token_refreshed notification
    refreshed = [n for n in harness.notifications() if n.get("method") == "cloud.token_refreshed"]
    assert refreshed, "expected cloud.token_refreshed notification"


def test_submit_otp_without_pending_login_errors(harness, stub_sncloud):
    resp = harness.call("cloud.submit_otp", {"code": "111111"})
    assert "error" in resp
    assert resp["error"]["code"] == -32014


def test_logout_clears_state(harness, stub_sncloud):
    harness.call("cloud.login", {"email": "a@b.c", "password": "pw"})
    resp = harness.call("cloud.logout")
    assert resp["result"]["ok"] is True


def test_login_token_validates_against_remote(harness, stub_sncloud):
    # The stub's ls() returns whatever's in self.listing — empty by default,
    # which counts as success (no exception thrown).
    resp = harness.call("cloud.login_token", {"token": "abc"})
    assert resp["result"]["ok"] is True
