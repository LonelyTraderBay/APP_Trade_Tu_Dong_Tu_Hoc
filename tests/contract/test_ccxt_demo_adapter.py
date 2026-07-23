"""Contract: CCXT DEMO adapter with fake exchange."""

from __future__ import annotations

from decimal import Decimal

import pytest

from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.domain.allowlist import D1B_ALLOWLIST, AllowlistViolation


@pytest.mark.d1b
def test_ccxt_demo_place_query_cancel() -> None:
    fake = FakeCcxtExchange()
    adapter = CcxtDemoAdapter(exchange=fake, endpoint="binance_spot_testnet")
    adapter.connect()
    order = adapter.place_order(
        client_order_id="cid-1",
        symbol=D1B_ALLOWLIST.symbol,
        side="buy",
        qty=Decimal("0.01"),
    )
    assert order["broker_order_id"]
    assert adapter.query_order_by_client_id("cid-1") is not None
    # idempotent
    again = adapter.place_order(
        client_order_id="cid-1",
        symbol=D1B_ALLOWLIST.symbol,
        side="buy",
        qty=Decimal("0.01"),
    )
    assert again["broker_order_id"] == order["broker_order_id"]
    opens = adapter.list_open_orders()
    assert "items" in opens
    execs = adapter.list_executions()
    assert execs["items"]
    canceled = adapter.cancel_order(broker_order_id=order["broker_order_id"])
    assert canceled["state"] == "CANCELED"


@pytest.mark.d1b
def test_sandbox_guard_on_connect() -> None:
    adapter = CcxtDemoAdapter(exchange=FakeCcxtExchange(), endpoint="https://api.binance.com")
    with pytest.raises(AllowlistViolation):
        adapter.connect()
