"""Contract: allowlist negatives."""

from __future__ import annotations

from decimal import Decimal

import pytest

from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.adapters.ccxt_demo.sandbox import assert_demo_sandbox
from autotrade.core.domain.allowlist import (
    D1B_ALLOWLIST,  # noqa: F401 — clarity
    AllowlistViolation,
)


@pytest.mark.d1b
def test_production_endpoint_refused() -> None:
    with pytest.raises(AllowlistViolation):
        assert_demo_sandbox("https://api.binance.com")


@pytest.mark.d1b
def test_place_wrong_symbol_refused() -> None:
    adapter = CcxtDemoAdapter(exchange=FakeCcxtExchange(), endpoint="binance_spot_testnet")
    adapter.connect()
    with pytest.raises(AllowlistViolation):
        adapter.place_order(
            client_order_id="c1",
            symbol="ETH/USDT",
            side="buy",
            qty=Decimal("0.001"),
        )


@pytest.mark.d1b
def test_live_mode_refused_on_allowlist() -> None:
    from autotrade.core.domain.allowlist import assert_allowlisted

    with pytest.raises(AllowlistViolation):
        assert_allowlisted(
            exchange_id="binance",
            market="spot",
            endpoint_class="binance_spot_testnet",
            symbol="BTC/USDT",
            mode="LIVE",
        )
