"""Allowlist unit tests."""

from __future__ import annotations

import pytest

from autotrade.core.domain.allowlist import (
    D1B_ALLOWLIST,
    AllowlistViolation,
    assert_allowlisted,
)


@pytest.mark.d1b
def test_allowlist_accepts_locked_tuple() -> None:
    assert_allowlisted(
        exchange_id=D1B_ALLOWLIST.exchange_id,
        market=D1B_ALLOWLIST.market,
        endpoint_class=D1B_ALLOWLIST.endpoint_class,
        symbol=D1B_ALLOWLIST.symbol,
        timeframe=D1B_ALLOWLIST.timeframe,
        mode="DEMO",
    )


@pytest.mark.d1b
@pytest.mark.parametrize(
    "kwargs",
    [
        {"exchange_id": "bybit"},
        {"symbol": "ETH/USDT"},
        {"timeframe": "5m"},
        {"mode": "LIVE"},
        {"endpoint_class": "binance_prod"},
    ],
)
def test_allowlist_rejects(kwargs: dict) -> None:
    base = {
        "exchange_id": D1B_ALLOWLIST.exchange_id,
        "market": D1B_ALLOWLIST.market,
        "endpoint_class": D1B_ALLOWLIST.endpoint_class,
        "symbol": D1B_ALLOWLIST.symbol,
        "timeframe": D1B_ALLOWLIST.timeframe,
        "mode": "DEMO",
    }
    base.update(kwargs)
    with pytest.raises(AllowlistViolation):
        assert_allowlisted(**base)
