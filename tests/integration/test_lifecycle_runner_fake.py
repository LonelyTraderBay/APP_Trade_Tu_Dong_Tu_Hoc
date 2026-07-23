"""Fake-backed lifecycle runner (no network) — verifies round-trip + real_testnet count."""

from __future__ import annotations

import pytest

from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.certify.lifecycle import count_real_lifecycles
from autotrade.core.certify.real_lifecycles import run_round_trip_lifecycles
from autotrade.core.domain.money import d


@pytest.mark.d1b
def test_lifecycle_runner_fake_counts_real_source(migrated_uow) -> None:  # noqa: ANN001
    fake = FakeCcxtExchange(last_price=d("50000"))
    adapter = CcxtDemoAdapter(exchange=fake, endpoint="binance_spot_testnet")
    adapter.connect()
    result = run_round_trip_lifecycles(
        uow=migrated_uow,
        adapter=adapter,
        account_id="demo1",
        count=3,
        source="real_testnet",
    )
    assert result.errors == []
    assert result.completed == 3
    assert result.total_real_count == 3
    with migrated_uow.session() as session:
        assert count_real_lifecycles(session, account_id="demo1") == 3


@pytest.mark.d1b
def test_lifecycle_runner_mock_source_does_not_count(migrated_uow) -> None:  # noqa: ANN001
    fake = FakeCcxtExchange(last_price=d("50000"))
    adapter = CcxtDemoAdapter(exchange=fake, endpoint="binance_spot_testnet")
    adapter.connect()
    result = run_round_trip_lifecycles(
        uow=migrated_uow,
        adapter=adapter,
        account_id="demo1",
        count=2,
        source="mock",
    )
    assert result.completed == 2
    with migrated_uow.session() as session:
        assert count_real_lifecycles(session, account_id="demo1") == 0
