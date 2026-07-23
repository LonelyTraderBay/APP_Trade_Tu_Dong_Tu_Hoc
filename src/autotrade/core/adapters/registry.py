"""Built-in adapter registry — Paper + certified CCXT DEMO only."""

from __future__ import annotations

from typing import Any

from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter
from autotrade.core.adapters.ccxt_demo.manifest import CCXT_DEMO_MANIFEST
from autotrade.core.adapters.manifest import PAPER_MANIFEST
from autotrade.core.adapters.paper import PaperAdapter
from autotrade.core.domain.allowlist import AllowlistViolation


def list_builtin_adapters() -> list[dict[str, Any]]:
    return [
        {
            "adapter_id": PAPER_MANIFEST.adapter_id,
            "modes": list(PAPER_MANIFEST.modes),
            "certified_trading": True,
        },
        {
            "adapter_id": CCXT_DEMO_MANIFEST.adapter_id,
            "exchange_id": CCXT_DEMO_MANIFEST.exchange_id,
            "modes": list(CCXT_DEMO_MANIFEST.modes),
            "endpoint_class": CCXT_DEMO_MANIFEST.endpoint_class,
            "certified_trading": True,
            "tuple": CCXT_DEMO_MANIFEST.endpoint_class,
        },
    ]


def create_adapter(adapter_id: str, **kwargs: Any) -> PaperAdapter | CcxtDemoAdapter:
    if adapter_id == "paper":
        return PaperAdapter(**kwargs)
    if adapter_id == "ccxt":
        return CcxtDemoAdapter(**kwargs)
    raise AllowlistViolation(f"uncertified adapter_id: {adapter_id}")
