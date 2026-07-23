"""D1b phase boundary — LIVE / second exchange refused."""

from __future__ import annotations

import pytest

from autotrade.core.adapters.registry import create_adapter, list_builtin_adapters
from autotrade.core.domain.allowlist import AllowlistViolation, D1B_ALLOWLIST, assert_allowlisted


@pytest.mark.d1b
def test_builtin_ccxt_metadata_exposes_full_tuple() -> None:
    ccxt = next(a for a in list_builtin_adapters() if a["adapter_id"] == "ccxt")
    assert ccxt["tuple"] == D1B_ALLOWLIST.canonical_key
    assert ccxt["tuple"] == "binance|spot|binance_spot_testnet|BTC/USDT|15m"
    assert ccxt["endpoint_class"] == D1B_ALLOWLIST.endpoint_class


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
