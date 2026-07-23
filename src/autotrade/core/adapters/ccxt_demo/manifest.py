"""CCXT DEMO adapter manifest (Binance Spot Testnet only)."""

from __future__ import annotations

from dataclasses import dataclass

from autotrade.core.domain.allowlist import D1B_ALLOWLIST


@dataclass(frozen=True, slots=True)
class CcxtDemoManifest:
    adapter_id: str = "ccxt"
    exchange_id: str = D1B_ALLOWLIST.exchange_id
    display_name: str = "Crypto (CCXT) Binance Spot Testnet"
    modes: tuple[str, ...] = ("DEMO",)
    markets: tuple[str, ...] = ("spot",)
    endpoint_class: str = D1B_ALLOWLIST.endpoint_class
    symbol: str = D1B_ALLOWLIST.symbol
    timeframe: str = D1B_ALLOWLIST.timeframe
    capabilities: tuple[str, ...] = (
        "place",
        "cancel",
        "query_by_client_id",
        "list_open_orders",
        "list_executions",
        "positions",
        "balances",
        "ohlcv_closed",
        "protection",
    )


CCXT_DEMO_MANIFEST = CcxtDemoManifest()
