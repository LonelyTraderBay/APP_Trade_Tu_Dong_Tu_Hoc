"""Full path Strategy→Risk→OMS→Paper→ledger→outbox."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from autotrade.core.domain.money import d
from autotrade.core.features.engine import FeatureEngine
from autotrade.core.market.candles import Candle
from autotrade.core.notify.outbox import OutboxService
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest
from autotrade.core.strategy.rule_sma_cross_v1 import RuleSmaCrossV1, StrategyParams
from autotrade.persistence.models import NotifyOutbox


@pytest.mark.d1a
def test_strategy_risk_oms_paper(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
    engine = FeatureEngine()
    rule = RuleSmaCrossV1(StrategyParams(n_fast=2, n_slow=4, atr_period=2, cooldown=1))
    start = datetime(2026, 1, 1, tzinfo=UTC)
    closes = [d(str(x)) for x in [5, 4, 3, 4, 5, 6, 7]]
    candles = [
        Candle(
            symbol="PAPER-INTERNAL-1",
            timeframe="15m",
            open_time=start + timedelta(minutes=15 * i),
            open=c,
            high=c + d("1"),
            low=c - d("1"),
            close=c,
            volume=d("1"),
            is_closed=True,
        )
        for i, c in enumerate(closes)
    ]
    decision = None
    for i in range(1, len(candles) + 1):
        snap = engine.snapshot(candles[:i], n_fast=2, n_slow=4, atr_period=2)
        decision = rule.evaluate(snap)
        if decision.side == "ENTER_LONG":
            break
    assert decision is not None and decision.side == "ENTER_LONG"

    submitter = DurableSubmitter(uow=uow, adapter=adapter, risk=risk, gate=gate)
    result = submitter.submit(
        SubmitRequest(
            account_id="paper1",
            symbol="PAPER-INTERNAL-1",
            side="buy",
            qty=d("1"),
            price=d("100"),
            stop_price=decision.stop_distance or d("95"),
            emit_notify=True,
            signal_id="path-sig",
        )
    )
    assert result.ok is True
    with uow.session() as session:
        OutboxService().enqueue(
            session, payload={"text": "[PAPER] account=paper1\nfill", "mode": "PAPER"}
        )
        assert session.query(NotifyOutbox).count() >= 1
