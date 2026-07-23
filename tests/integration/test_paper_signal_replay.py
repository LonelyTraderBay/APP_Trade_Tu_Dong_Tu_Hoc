"""Integration: closed candles → features → rule_sma_cross_v1 signals (no OMS)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from autotrade.core.domain.money import d
from autotrade.core.features.engine import FeatureEngine
from autotrade.core.market.candles import Candle, CandleStore
from autotrade.core.market.instruments import PAPER_INTERNAL_1, paper_internal_1
from autotrade.core.strategy.rule_sma_cross_v1 import RuleSmaCrossV1, StrategyParams


def test_paper_signal_replay_deterministic() -> None:
    instrument = paper_internal_1()
    assert instrument.internal_symbol == PAPER_INTERNAL_1

    def run_once() -> list[str]:
        store = CandleStore()
        engine = FeatureEngine()
        rule = RuleSmaCrossV1(StrategyParams(n_fast=2, n_slow=4, atr_period=2, cooldown=1))
        start = datetime(2026, 1, 1, tzinfo=UTC)
        closes = [d(str(x)) for x in [5, 4, 3, 4, 5, 6, 7, 6, 5, 4]]
        sides: list[str] = []
        for i, close in enumerate(closes):
            store.ingest(
                Candle(
                    symbol=PAPER_INTERNAL_1,
                    timeframe="15m",
                    open_time=start + timedelta(minutes=15 * i),
                    open=close,
                    high=close + d("0.5"),
                    low=close - d("0.5"),
                    close=close,
                    volume=d("1"),
                    is_closed=True,
                )
            )
            closed = store.closed_only(PAPER_INTERNAL_1, "15m")
            snap = engine.snapshot(closed, n_fast=2, n_slow=4, atr_period=2)
            sides.append(rule.evaluate(snap).side)
        return sides

    assert run_once() == run_once()
