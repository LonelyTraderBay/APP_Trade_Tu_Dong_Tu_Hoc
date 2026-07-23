"""Unit tests for rule_sma_cross_v1."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from autotrade.core.domain.money import d
from autotrade.core.features.engine import FeatureEngine
from autotrade.core.market.candles import Candle
from autotrade.core.strategy.rule_sma_cross_v1 import RuleSmaCrossV1, StrategyParams


def _candles(closes: list[Decimal]) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    out: list[Candle] = []
    for i, close in enumerate(closes):
        out.append(
            Candle(
                symbol="PAPER-INTERNAL-1",
                timeframe="15m",
                open_time=start + timedelta(minutes=15 * i),
                open=close,
                high=close + d("1"),
                low=close - d("1"),
                close=close,
                volume=d("10"),
                is_closed=True,
            )
        )
    return out


def test_abstain_insufficient_and_enter_exit_cooldown() -> None:
    engine = FeatureEngine()
    rule = RuleSmaCrossV1(StrategyParams(n_fast=2, n_slow=4, atr_period=2, cooldown=2))

    # Build a downtrend then upcross then downcross.
    series = [d(str(x)) for x in [10, 9, 8, 7, 8, 9, 10, 11, 10, 9, 8, 7]]
    decisions = []
    for i in range(1, len(series) + 1):
        snap = engine.snapshot(
            _candles(series[:i]),
            n_fast=2,
            n_slow=4,
            atr_period=2,
        )
        decisions.append(rule.evaluate(snap).side)

    assert "ABSTAIN" in decisions
    assert "ENTER_LONG" in decisions
    assert "EXIT_LONG" in decisions


def test_open_candle_rejected_by_feature_engine() -> None:
    engine = FeatureEngine()
    candles = _candles([d("10"), d("11"), d("12")])
    open_last = Candle(
        symbol=candles[-1].symbol,
        timeframe=candles[-1].timeframe,
        open_time=candles[-1].open_time,
        open=candles[-1].open,
        high=candles[-1].high,
        low=candles[-1].low,
        close=candles[-1].close,
        volume=candles[-1].volume,
        is_closed=False,
    )
    assert engine.snapshot(
        [*candles[:-1], open_last], n_fast=2, n_slow=2, atr_period=2
    ) is None
