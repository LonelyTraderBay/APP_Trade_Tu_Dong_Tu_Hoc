"""Unit tests for rule_sma_cross_v1."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from autotrade.core.domain.money import d
from autotrade.core.features.engine import FeatureEngine
from autotrade.core.market.candles import Candle
from autotrade.core.strategy.rule_sma_cross_v1 import (
    RuleSmaCrossV1,
    SignalDecision,
    StrategyParams,
)


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


@pytest.mark.d1a
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


@pytest.mark.d1a
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


# --- SC-006 reference series -------------------------------------------------
#
# closes:      10  9  8  7  6  7  8  9  8  7  6  5  4  5  6
# index (i):    1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
#
# `_candles()` sets high = close+1, low = close-1 for every bar, and every
# consecutive close in this series steps by exactly +-1 (a down-leg, an
# up-leg, another down-leg, another up-leg). For a step dc = close_i -
# close_{i-1} of magnitude 1, true range = max(high-low, |high-prev_close|,
# |low-prev_close|) = max(2, |dc+1|, |dc-1|):
#   dc = +1 -> max(2, 2, 0) = 2
#   dc = -1 -> max(2, 0, 2) = 2
# so TR is exactly 2 on every bar of this series, and therefore ATR (a plain
# average of TR over any window, per `_atr()`) is exactly 2 wherever it is
# defined. With the default k = 1.5, the ATR-stop distance on any entry in
# this series is therefore exactly Decimal("2") * Decimal("1.5") = 3.0 -- an
# independently hand-derived number, not merely "a stop exists".
#
# With n_fast=2, n_slow=4, atr_period=2, cooldown=3 (cooldown overridden to
# match SC-006's "cooldown" dimension; k left at its production default of
# 1.5 to also exercise the real ATR-stop multiplier):
#
#   i=1..3  : insufficient_history (sma_slow/atr not yet defined)
#   i=4..6  : no_cross (fast stays below slow through the down-leg)
#   i=7     : ENTER_LONG  (fast 7.5 crosses above slow 7.0), stop = 2*1.5=3.0
#   i=8..9  : no_cross (still in position, no cross)
#   i=10    : EXIT_LONG   (fast 7.5 crosses below slow 8.0), cooldown set to 3
#   i=11..13: cooldown (exactly params.cooldown=3 bars)
#   i=14    : no_cross (cooldown has expired; ordinary cross-check resumes)
#   i=15    : ENTER_LONG again (fast 5.5 crosses above slow 5.0), stop = 3.0
#
# (Every fast/slow SMA value above was computed by hand from the closes list
# using plain arithmetic means over the trailing n_fast/n_slow window.)
_REFERENCE_CLOSES = [d(str(x)) for x in [10, 9, 8, 7, 6, 7, 8, 9, 8, 7, 6, 5, 4, 5, 6]]
_REFERENCE_PARAMS = StrategyParams(n_fast=2, n_slow=4, atr_period=2, cooldown=3)


def _run_reference_series() -> list[SignalDecision]:
    engine = FeatureEngine()
    rule = RuleSmaCrossV1(_REFERENCE_PARAMS)
    decisions: list[SignalDecision] = []
    for i in range(1, len(_REFERENCE_CLOSES) + 1):
        snap = engine.snapshot(
            _candles(_REFERENCE_CLOSES[:i]),
            n_fast=_REFERENCE_PARAMS.n_fast,
            n_slow=_REFERENCE_PARAMS.n_slow,
            atr_period=_REFERENCE_PARAMS.atr_period,
        )
        decisions.append(rule.evaluate(snap))
    return decisions


@pytest.mark.d1a
def test_enter_long_on_sma_crossover() -> None:
    """Crossover entry: ENTER_LONG fires exactly on the bar where fast SMA
    crosses from <= slow SMA to > slow SMA, and not before."""
    decisions = _run_reference_series()
    # No entry signal anywhere before the hand-derived crossover bar (i=7,
    # 0-indexed 6).
    assert [dec.side for dec in decisions[:6]] == ["ABSTAIN"] * 6
    entry = decisions[6]
    assert entry.side == "ENTER_LONG"
    assert entry.reason == "sma_cross_up"


@pytest.mark.d1a
def test_atr_stop_distance_equals_k_times_atr_on_entry() -> None:
    """ATR-stop distance is genuinely entry_price +- k*ATR: for this series
    ATR is hand-derived to be exactly 2 (see module comment above), so with
    the production default k=1.5 the stop distance must equal exactly 3.0 --
    not merely "some stop value"."""
    decisions = _run_reference_series()
    expected_stop = d("2") * StrategyParams().k  # k defaults to 1.5 -> 3.0
    assert expected_stop == d("3.0")

    first_entry = decisions[6]  # i=7
    assert first_entry.side == "ENTER_LONG"
    assert first_entry.stop_distance == expected_stop

    second_entry = decisions[14]  # i=15, re-entry after cooldown expires
    assert second_entry.side == "ENTER_LONG"
    assert second_entry.stop_distance == expected_stop


@pytest.mark.d1a
def test_exit_long_on_bearish_crossover_while_in_position() -> None:
    """Exit condition: EXIT_LONG fires exactly on the bar where fast SMA
    crosses from >= slow SMA to < slow SMA while a long position is open."""
    decisions = _run_reference_series()
    exit_decision = decisions[9]  # i=10
    assert exit_decision.side == "EXIT_LONG"
    assert exit_decision.reason == "sma_cross_down"
    # EXIT_LONG carries no stop distance of its own.
    assert exit_decision.stop_distance is None


@pytest.mark.d1a
def test_cooldown_lasts_exactly_configured_bars() -> None:
    """Cooldown period length: after EXIT_LONG, exactly
    `params.cooldown` (=3) consecutive bars must ABSTAIN with
    reason="cooldown", and the very next bar after that must resume ordinary
    cross detection (not still be in cooldown) -- proving the suppression
    window is exactly N bars, neither shorter nor longer."""
    decisions = _run_reference_series()
    assert decisions[9].side == "EXIT_LONG"  # i=10

    cooldown_window = decisions[10:13]  # i=11, i=12, i=13
    assert len(cooldown_window) == _REFERENCE_PARAMS.cooldown
    assert [dec.side for dec in cooldown_window] == ["ABSTAIN"] * 3
    assert [dec.reason for dec in cooldown_window] == ["cooldown"] * 3

    # i=14: cooldown has expired -- reason must no longer be "cooldown".
    post_cooldown = decisions[13]
    assert post_cooldown.side == "ABSTAIN"
    assert post_cooldown.reason != "cooldown"

    # i=15: a new entry is allowed again now that cooldown has elapsed.
    resumed_entry = decisions[14]
    assert resumed_entry.side == "ENTER_LONG"


@pytest.mark.d1a
def test_abstain_reasons_before_sufficient_history() -> None:
    """Abstain case: while sma_slow/atr are not yet defined, every decision
    must be ABSTAIN with reason="insufficient_history" -- not "no_cross"."""
    decisions = _run_reference_series()
    for dec in decisions[:3]:  # i=1..3
        assert dec.side == "ABSTAIN"
        assert dec.reason == "insufficient_history"


@pytest.mark.d1a
def test_never_emits_short_signal_on_downward_crossover() -> None:
    """Long-only is a hard rule (G1.4/G4.1): even when a clean downward SMA
    crossover occurs while flat (no long position open), the strategy must
    never open a short -- it must ABSTAIN. `SignalDecision.side` has no
    short-side value at all, but this test proves the *behavior*, not just
    the type: on a textbook bearish cross with nothing open, no ENTER_LONG
    fires either (that would be wrong-direction) and no exception/short
    side leaks out -- the strategy simply sits out."""
    # Mirror of the reference series: up-leg then down-leg, so the fast SMA
    # crosses from >= slow SMA to < slow SMA (a textbook bearish crossover)
    # while the rule has never entered a position.
    closes = [d(str(x)) for x in [10, 11, 12, 13, 14, 13, 12]]
    engine = FeatureEngine()
    rule = RuleSmaCrossV1(StrategyParams(n_fast=2, n_slow=4, atr_period=2, cooldown=3))

    decisions: list[SignalDecision] = []
    for i in range(1, len(closes) + 1):
        snap = engine.snapshot(_candles(closes[:i]), n_fast=2, n_slow=4, atr_period=2)
        decisions.append(rule.evaluate(snap))

    allowed_sides = {"ENTER_LONG", "EXIT_LONG", "ABSTAIN"}
    assert {dec.side for dec in decisions} <= allowed_sides
    assert not any("SHORT" in dec.side or "SELL" in dec.side for dec in decisions)

    # i=7 (0-indexed 6): the bearish cross bar. Fast (12.5) crosses below
    # slow (13.0) coming from fast(13.5) >= slow(13.0) on the prior bar --
    # a genuine bearish crossover -- but since the rule was never in a long
    # position, it must ABSTAIN rather than opening a short.
    bearish_cross_bar = decisions[6]
    assert bearish_cross_bar.side == "ABSTAIN"
    assert rule._in_position is False
