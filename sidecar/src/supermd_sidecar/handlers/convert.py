"""convert.* RPC methods — wrap the supermd engine and stream progress as
notifications.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Dict

from supermd_sidecar.rpc import Handler, RpcContext, rpc_error
from supermd_sidecar.state import ConversionTask, SidecarState

log = logging.getLogger(__name__)


def _build_engine_config(overrides: Dict[str, Any]):
    """Build a SuperMDConfig from a dict the host sent. Falls back to engine
    defaults for any unset field."""
    from supermd.config import SuperMDConfig

    return SuperMDConfig(**(overrides or {}))


def register(state: SidecarState) -> Dict[str, Handler]:

    def _convert_one(task: ConversionTask, model: str | None,
                     force: bool, config_overrides: Dict[str, Any]) -> None:
        from supermd.converter import convert_file
        from supermd.importers import get_extractor
        from supermd.metadata_db import (
            MetadataManager,
            InputNotChangedError,
            OutputChangedError,
        )

        cfg = _build_engine_config(config_overrides)
        extractor = get_extractor(task.file)
        if extractor is None:
            state.emit(
                "convert.failed",
                {"task_id": task.task_id, "error": f"no extractor for: {task.file}"},
            )
            return

        state.emit(
            "convert.started",
            {"task_id": task.task_id, "file": task.file, "output": task.output},
        )
        task.status = "running"
        started = time.monotonic()
        manager = MetadataManager(task.output)
        try:
            convert_file(
                extractor,
                task.file,
                task.output,
                cfg,
                force=force,
                model=model or cfg.model,
                metadata_manager=manager,
                cooldown=cfg.defaults.cooldown,
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            state.emit(
                "convert.finished",
                {"task_id": task.task_id, "duration_ms": duration_ms},
            )
            task.status = "done"
        except InputNotChangedError:
            state.emit(
                "convert.skipped",
                {"task_id": task.task_id, "reason": "input_unchanged"},
            )
            task.status = "done"
        except OutputChangedError as e:
            state.emit(
                "convert.skipped",
                {"task_id": task.task_id, "reason": "output_modified", "detail": str(e)},
            )
            task.status = "done"
        except Exception as e:  # noqa: BLE001
            state.emit(
                "convert.failed",
                {
                    "task_id": task.task_id,
                    "error": f"{type(e).__name__}: {e}",
                    "traceback": traceback.format_exc(),
                },
            )
            task.status = "failed"
        finally:
            manager.close()

    def file_(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        input_path = params.get("input")
        output_path = params.get("output")
        if not input_path or not output_path:
            raise rpc_error(-32602, "input and output are required")
        if not os.path.exists(input_path):
            raise rpc_error(-32020, f"input not found: {input_path}")

        task_id = state.new_task_id("conv")
        task = ConversionTask(task_id=task_id, file=input_path, output=output_path)
        state.conversion_tasks[task_id] = task

        threading.Thread(
            target=_convert_one,
            args=(task, params.get("model"), bool(params.get("force")),
                  params.get("config") or {}),
            name=f"convert-{task_id}",
            daemon=True,
        ).start()
        return {"task_id": task_id, "queued": True}

    def directory(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        from supermd.importers import SUPPORTED_EXTENSIONS

        input_dir = params.get("input")
        output_path = params.get("output")
        if not input_dir or not output_path:
            raise rpc_error(-32602, "input and output are required")
        if not os.path.isdir(input_dir):
            raise rpc_error(-32021, f"input is not a directory: {input_dir}")

        # Walk the directory and queue one task per file. The engine has its
        # own batch entry point but we want per-file events for the UI.
        tasks: list[str] = []
        for root, _, files in os.walk(input_dir):
            for f in sorted(files):
                if f.lower().endswith(SUPPORTED_EXTENSIONS):
                    full = os.path.join(root, f)
                    task_id = state.new_task_id("conv")
                    task = ConversionTask(task_id=task_id, file=full, output=output_path)
                    state.conversion_tasks[task_id] = task
                    tasks.append(task_id)
                    threading.Thread(
                        target=_convert_one,
                        args=(task, params.get("model"), bool(params.get("force")),
                              params.get("config") or {}),
                        name=f"convert-{task_id}",
                        daemon=True,
                    ).start()
        return {"task_ids": tasks, "files": len(tasks)}

    def cancel(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        task_id = params.get("task_id")
        task = state.conversion_tasks.get(task_id)
        if task is None:
            raise rpc_error(-32022, f"unknown task_id: {task_id}")
        task.cancel_event.set()
        return {"ok": True}

    def list_active(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "tasks": [
                {
                    "task_id": t.task_id,
                    "file": t.file,
                    "output": t.output,
                    "status": t.status,
                }
                for t in state.conversion_tasks.values()
            ]
        }

    def rebuild_metadata(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        from supermd.converter import rebuild_metadata_directory

        input_path = params.get("input")
        output_path = params.get("output")
        if not input_path or not output_path:
            raise rpc_error(-32602, "input and output are required")
        cfg = _build_engine_config(params.get("config") or {})
        rebuild_metadata_directory(input_path, output_path, cfg)
        return {"ok": True}

    def clean_metadata(ctx: RpcContext, params: Dict[str, Any]) -> Dict[str, Any]:
        from supermd.converter import clean_metadata_directory

        output_path = params.get("output")
        if not output_path:
            raise rpc_error(-32602, "output is required")
        clean_metadata_directory(output_path)
        return {"ok": True}

    return {
        "convert.file": file_,
        "convert.directory": directory,
        "convert.cancel": cancel,
        "convert.list_active": list_active,
        "convert.rebuild_metadata": rebuild_metadata,
        "convert.clean_metadata": clean_metadata,
    }
