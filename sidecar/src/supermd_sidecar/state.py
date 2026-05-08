"""Long-lived sidecar state — owns the cloud client, conversion task table,
config path, and a reference to the RPC emitter so handlers can push events.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from platformdirs import user_config_path, user_log_path

log = logging.getLogger(__name__)


@dataclass
class ConversionTask:
    task_id: str
    file: str
    output: str
    status: str = "queued"  # queued | running | done | failed | cancelled
    cancel_event: threading.Event = field(default_factory=threading.Event)


@dataclass
class CloudSyncTask:
    task_id: str
    remote_path: str
    local_path: str
    interval_sec: int
    thread: Optional[threading.Thread] = None
    stop_event: threading.Event = field(default_factory=threading.Event)


class SidecarState:
    """Process-wide state. One instance per sidecar lifetime."""

    APP_DIR = "SuperMD"

    def __init__(self):
        self.config_dir: Path = user_config_path(self.APP_DIR, ensure_exists=True)
        self.log_dir: Path = user_log_path(self.APP_DIR, ensure_exists=True)
        self.config_path: Path = self.config_dir / "config.yaml"
        self.metadata_db: Path = self.config_dir / "metadata.sqlite"

        self._emit: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self._lock = threading.Lock()

        # Cloud client is created lazily on first cloud.* call
        self._cloud_client = None
        self._pending_otp: Optional[threading.Event] = None
        self._otp_code: Optional[str] = None
        self._otp_lock = threading.Lock()

        # Active tasks
        self.conversion_tasks: Dict[str, ConversionTask] = {}
        self.sync_tasks: Dict[str, CloudSyncTask] = {}

    # ------------------------------------------------------------------
    # Emitter wiring
    # ------------------------------------------------------------------

    def bind_emitter(self, emit: Callable[[str, Dict[str, Any]], None]) -> None:
        self._emit = emit

    def emit(self, method: str, params: Dict[str, Any]) -> None:
        if self._emit is None:
            log.warning("emit before emitter bound: %s", method)
            return
        self._emit(method, params)

    # ------------------------------------------------------------------
    # Cloud client
    # ------------------------------------------------------------------

    def get_cloud_client(self):
        with self._lock:
            if self._cloud_client is None:
                # Imported lazily so the sidecar starts even if sncloud is absent
                # in dev environments.
                from sncloud import SNClient

                self._cloud_client = SNClient()
            return self._cloud_client

    def reset_cloud_client(self) -> None:
        with self._lock:
            self._cloud_client = None

    def request_otp(self) -> str:
        """Block the calling thread until the host sends an OTP code via
        ``cloud.submit_otp``. Single-flight: only one OTP request can be in
        flight per process.
        """
        with self._otp_lock:
            self._otp_code = None
            self._pending_otp = threading.Event()

        if self._pending_otp.wait(timeout=300):  # 5min
            with self._otp_lock:
                code = self._otp_code or ""
                self._otp_code = None
                self._pending_otp = None
            return code
        # Timeout
        with self._otp_lock:
            self._pending_otp = None
        raise TimeoutError("OTP entry timed out")

    def submit_otp(self, code: str) -> None:
        with self._otp_lock:
            if self._pending_otp is None:
                raise RuntimeError("no OTP request is pending")
            self._otp_code = code
            self._pending_otp.set()

    # ------------------------------------------------------------------
    # Task tracking
    # ------------------------------------------------------------------

    def new_task_id(self, prefix: str = "task") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8]}"

    def shutdown(self) -> None:
        log.info("Shutting down sidecar state")
        for task in self.sync_tasks.values():
            task.stop_event.set()
        for task in self.conversion_tasks.values():
            task.cancel_event.set()
