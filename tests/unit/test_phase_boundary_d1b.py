"""D1b phase boundary — LIVE / second exchange refused."""

from __future__ import annotations

import pytest

from autotrade.core.adapters.registry import create_adapter
from autotrade.core.domain.allowlist import AllowlistViolation, assert_allowlisted


@pytest.mark.d1b
def test_live_hard_disabled() -> None:
    with pytest.raises(AllowlistViolation):
        assert_allowlisted(
            exchange_id="binance",
            market="spot",
            endpoint_class="binance_spot_testnet",
            symbol="BTC/USDT",
            mode="LIVE",
        )


@pytest.mark.d1b
def test_second_exchange_adapter_refused() -> None:
    with pytest.raises(AllowlistViolation):
        create_adapter("bybit")
