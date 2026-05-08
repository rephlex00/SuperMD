"""Handler registry. Each topic module exposes a ``register(state)`` function
that returns a dict of {method_name: handler}. Top-level dispatch table is
the union of all topics."""

from __future__ import annotations

from typing import Dict

from supermd_sidecar.rpc import Handler
from supermd_sidecar.state import SidecarState

from . import system, llm, obsidian, cloud, convert, config


def build_dispatch_table(state: SidecarState) -> Dict[str, Handler]:
    table: Dict[str, Handler] = {}
    for module in (system, llm, obsidian, cloud, convert, config):
        table.update(module.register(state))
    return table
