"""Adapter capability manifest (D1a Paper)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AdapterManifest:
    adapter_id: str
    modes: tuple[str, ...]
    capabilities: tuple[str, ...]
    instrument_model: str
    extra: dict[str, Any] = field(default_factory=dict)


PAPER_MANIFEST = AdapterManifest(
    adapter_id="paper",
    modes=("PAPER",),
    capabilities=(
        "place",
        "cancel",
        "query_by_client_id",
        "list_open_orders",
        "list_executions",
        "positions",
        "balances",
        "protective_orders",
    ),
    instrument_model="normalized_internal_symbol",
)
