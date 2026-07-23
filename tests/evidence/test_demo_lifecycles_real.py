"""Real-testnet lifecycle harness — skipped unless AUTOTRADE_D1B_REAL=1."""

from __future__ import annotations

import os

import pytest

from autotrade.core.certify.real_lifecycles import (
    build_real_adapter,
    lifecycle_count_from_env,
    run_round_trip_lifecycles,
)


@pytest.mark.d1b
@pytest.mark.skipif(os.environ.get("AUTOTRADE_D1B_REAL") != "1", reason="real DEMO only")
def test_demo_lifecycles_real(migrated_uow) -> None:  # noqa: ANN001
    """Owner-attended: round-trips on Binance Spot Testnet; count via env (default 2 smoke)."""
    adapter = build_real_adapter(account_id="demo-binance")
    adapter.connect()
    count = lifecycle_count_from_env(default=2)
    result = run_round_trip_lifecycles(
        uow=migrated_uow,
        adapter=adapter,
        account_id="demo-binance",
        count=count,
        source="real_testnet",
    )
    assert not result.errors, result.errors
    assert result.completed == count
    assert result.total_real_count >= count
