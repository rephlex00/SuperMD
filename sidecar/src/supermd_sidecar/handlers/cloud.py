"""cloud.* RPC methods — Supernote Cloud login and recurring sync.

Login flow with OTP:
  1. Host calls ``cloud.login`` with email + password.
  2. If account is on a new device, the sncloud library raises
     ``AuthenticationError("__E1760__:<timestamp>")``.
  3. Sidecar captures that, asks the cloud to send a verification email, then
     emits ``cloud.otp_required`` *as a notification*.
  4. The original ``cloud.login`` request blocks (in its handler thread) until
     either an OTP arrives via ``cloud.submit_otp`` or it times out.
  5. Once verified, sncloud returns a JWT and the sidecar emits
     ``cloud.token_refreshed`` so the host can persist it to the Keychain.

This whole dance is hidden from the SwiftUI app — it just shows a sheet when
``cloud.otp_required`` arrives and posts back the digits.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import threading
import time
from pathlib import Path, PurePosixPath
from typing import Any, Dict

from supermd_sidecar.rpc import Handler, RpcContext, rpc_error
from supermd_sidecar.state import CloudSyncTask, SidecarState

log = logging.getLogger(__name__)


def _login_with_otp(state: SidecarState, email: str, password: str) -> str:
    """Perform the email/password login, driving the OTP flow if needed.

    Returns the access token on success.
    """
    from sncloud.exceptions import AuthenticationError  # noqa: PLC0415

    client = state.get_cloud_client()

    try:
        client.login(email, password)
        return getattr(client, "_access_token", "") or ""
    except AuthenticationError as e:
        err = str(e)
        if not err.startswith("__E1760__:"):
            raise rpc_error(-32010, f"login failed: {e}")
        timestamp = err.split(":", 1)[1]

    # Trigger code dispatch
    try:
        valid_code_key = client.send_verification_code(email, timestamp)
    except Exception as e:  # noqa: BLE001
        log.warning("send_verification_code failed (will still wait for OTP): %s", e)
        valid_code_key = ""

    # Tell the host to prompt the user
    state.emit("cloud.otp_required", {"email": email})

    code = state.request_otp()
    if not code:
        raise rpc_error(-32011, "OTP entry cancelled or empty")

    try:
        token = client.verify_otp(email, code, valid_code_key, timestamp)
    except Exception as e:  # noqa: BLE001
        raise rpc_error(-32012, f"OTP rejected: {e}")

    client._access_token = token
    state.emit("cloud.token_refreshed", {"token": token})
    return token


def _sync_directory(client, remote_path: str, local_root: Path,
                    extensions=(".note", ".spd"), ctx_emit=None,
                    task_id: str | None = None) -> int:
    """Recursively sync files from remote → local. Returns count downloaded."""
    from sncloud.models import Directory, File  # noqa: PLC0415

    downloaded = 0
    try:
        items = client.ls(remote_path)
    except Exception as e:  # noqa: BLE001
        log.error("listing %s failed: %s", remote_path, e)
        return 0

    for item in items:
        if isinstance(item, Directory):
            child_remote = f"{remote_path}/{item.file_name}"
            child_local = local_root / item.file_name
            child_local.mkdir(parents=True, exist_ok=True)
            downloaded += _sync_directory(
                client, child_remote, child_local, extensions, ctx_emit, task_id
            )
            continue

        if not isinstance(item, File):
            continue
        if not item.file_name.lower().endswith(extensions):
            continue
        # Path traversal guard
        if (
            "/" in item.file_name
            or "\\" in item.file_name
            or item.file_name.startswith(".")
            or item.file_name != PurePosixPath(item.file_name).name
        ):
            log.warning("skipping suspicious filename: %r", item.file_name)
            continue

        local_file = local_root / item.file_name
        if local_file.exists():
            continue

        log.info("downloading %s/%s", remote_path, item.file_name)
        tmp_dir: Path | None = None
        try:
            tmp_dir = Path(tempfile.mkdtemp(dir=local_root))
            client.get(f"{remote_path}/{item.file_name}", tmp_dir)
            tmp_file = tmp_dir / item.file_name
            tmp_file.rename(local_file)
            downloaded += 1
            if ctx_emit and task_id:
                ctx_emit(
                    "cloud.file_downloaded",
                    {"task_id": task_id, "file": str(local_file)},
                )
        except Exception as e:  # noqa: BLE001
            log.error("downloading %s failed: %s", item.file_name, e)
        finally:
            if tmp_dir is not None and tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

    return downloaded


def register(state: SidecarState) -> Dict[str, Handler]:
    def login(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        email = params.get("email")
        password = params.get("password")
        if not email or not password:
            raise rpc_error(-32602, "email and password are required")
        token = _login_with_otp(state, email, password)
        return {"ok": True, "token": token, "email": email}

    def login_token(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        token = params.get("token")
        if not token:
            raise rpc_error(-32602, "token is required")
        client = state.get_cloud_client()
        client._access_token = token
        # Liveness check
        try:
            client.ls("/")
        except Exception as e:  # noqa: BLE001
            raise rpc_error(-32013, f"saved token rejected: {e}")
        return {"ok": True}

    def submit_otp(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        code = (params.get("code") or "").strip()
        if not code:
            raise rpc_error(-32602, "code is required")
        try:
            state.submit_otp(code)
        except RuntimeError as e:
            raise rpc_error(-32014, str(e))
        return {"ok": True}

    def list_remote(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        remote_path = params.get("path", "/")
        client = state.get_cloud_client()
        try:
            items = client.ls(remote_path)
        except Exception as e:  # noqa: BLE001
            raise rpc_error(-32015, f"ls failed: {e}")
        out = []
        for item in items:
            kind = type(item).__name__.lower()
            out.append({"name": item.file_name, "kind": kind})
        return {"items": out, "path": remote_path}

    def start_sync(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        remote_path = params.get("remote_path", "/Note")
        local_path = params.get("local_path")
        interval_sec = int(params.get("interval_sec", 300))
        if not local_path:
            raise rpc_error(-32602, "local_path is required")
        local = Path(local_path).expanduser()
        local.mkdir(parents=True, exist_ok=True)

        task_id = state.new_task_id("sync")
        task = CloudSyncTask(
            task_id=task_id,
            remote_path=remote_path,
            local_path=str(local),
            interval_sec=interval_sec,
        )

        def loop():
            client = state.get_cloud_client()
            while not task.stop_event.is_set():
                try:
                    count = _sync_directory(
                        client,
                        remote_path,
                        local,
                        ctx_emit=state.emit,
                        task_id=task_id,
                    )
                    state.emit(
                        "cloud.sync_progress",
                        {"task_id": task_id, "downloaded": count},
                    )
                except Exception as e:  # noqa: BLE001
                    log.error("sync error: %s", e)
                    state.emit(
                        "cloud.sync_error",
                        {"task_id": task_id, "error": str(e)},
                    )
                # Sleep but break early on stop
                task.stop_event.wait(timeout=interval_sec)

        thread = threading.Thread(target=loop, name=f"cloud-sync-{task_id}", daemon=True)
        task.thread = thread
        state.sync_tasks[task_id] = task
        thread.start()
        return {"task_id": task_id}

    def stop_sync(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        task_id = params.get("task_id")
        if not task_id:
            raise rpc_error(-32602, "task_id is required")
        task = state.sync_tasks.pop(task_id, None)
        if task is None:
            raise rpc_error(-32016, f"unknown task_id: {task_id}")
        task.stop_event.set()
        return {"ok": True}

    def logout(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        for task in list(state.sync_tasks.values()):
            task.stop_event.set()
        state.sync_tasks.clear()
        state.reset_cloud_client()
        return {"ok": True}

    return {
        "cloud.login": login,
        "cloud.login_token": login_token,
        "cloud.submit_otp": submit_otp,
        "cloud.list_remote": list_remote,
        "cloud.start_sync": start_sync,
        "cloud.stop_sync": stop_sync,
        "cloud.logout": logout,
    }
