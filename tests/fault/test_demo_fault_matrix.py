"""D1b fault matrix (inject on fake exchange)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.core.domain.money import d


@pytest.mark.d1b
def test_demo_auth_fail() -> None:
    fake = FakeCcxtExchange(fail_auth=True)
    adapter = CcxtDemoAdapter(exchange=fake, endpoint="binance_spot_testnet")
    with pytest.raises(RuntimeError, match="auth"):
        adapter.connect()


@pytest.mark.d1b
def test_demo_disconnect_on_place() -> None:
    fake = FakeCcxtExchange(disconnect=True)
    adapter = CcxtDemoAdapter(exchange=fake, endpoint="binance_spot_testnet")
    adapter.connect()
    with pytest.raises(RuntimeError, match="disconnect"):
        adapter.place_order(
            client_order_id="x",
            symbol=D1B_ALLOWLIST.symbol,
            side="buy",
            qty=Decimal("0.001"),
        )


@pytest.mark.d1b
def test_demo_rate_limit() -> None:
    fake = FakeCcxtExchange(rate_limited=True)
    adapter = CcxtDemoAdapter(exchange=fake, endpoint="binance_spot_testnet")
    adapter.connect()
    with pytest.raises(RuntimeError, match="rate_limit"):
        adapter.place_order(
            client_order_id="x",
            symbol=D1B_ALLOWLIST.symbol,
            side="buy",
            qty=Decimal("0.001"),
        )


@pytest.mark.d1b
def test_demo_partial_fill_inject() -> None:
    fake = FakeCcxtExchange(inject_partial_qty=d("0.0005"), last_price=d("50000"))
    adapter = CcxtDemoAdapter(exchange=fake, endpoint="binance_spot_testnet")
    adapter.connect()
    order = adapter.place_order(
        client_order_id="partial-1",
        symbol=D1B_ALLOWLIST.symbol,
        side="buy",
        qty=Decimal("0.001"),
    )
    assert order["state"] == "PARTIAL"
    assert d(order["filled_qty"]) == d("0.0005")
