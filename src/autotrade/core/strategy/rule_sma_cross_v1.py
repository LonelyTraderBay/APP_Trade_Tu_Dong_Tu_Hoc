"""Strategy rule_sma_cross_v1 — spot long-only, closed candles only."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from autotrade.core.domain.money import d
from autotrade.core.features.engine import FeatureSnapshot


@dataclass(frozen=True, slots=True)
class StrategyParams:
    n_fast: int = 10
    n_slow: int = 30
    atr_period: int = 14
    k: Decimal = d("1.5")
    cooldown: int = 3


@dataclass(frozen=True, slots=True)
class SignalDecision:
    side: str  # ENTER_LONG | EXIT_LONG | ABSTAIN
    stop_distance: Decimal | None = None
    reason: str = ""


@dataclass
class RuleSmaCrossV1:
    params: StrategyParams = StrategyParams()
    _prev_fast: Decimal | None = None
    _prev_slow: Decimal | None = None
    _in_position: bool = False
    _cooldown_left: int = 0

    def evaluate(self, snap: FeatureSnapshot | None) -> SignalDecision:
        if snap is None:
            return SignalDecision("ABSTAIN", reason="no_snapshot")
        if snap.sma_fast is None or snap.sma_slow is None or snap.atr is None:
            return SignalDecision("ABSTAIN", reason="insufficient_history")

        fast, slow = snap.sma_fast, snap.sma_slow
        stop = snap.atr * self.params.k

        if self._cooldown_left > 0:
            self._cooldown_left -= 1
            self._prev_fast, self._prev_slow = fast, slow
            return SignalDecision("ABSTAIN", reason="cooldown")

        decision = SignalDecision("ABSTAIN", reason="no_cross")
        if self._prev_fast is not None and self._prev_slow is not None:
            bullish = self._prev_fast <= self._prev_slow and fast > slow
            bearish = self._prev_fast >= self._prev_slow and fast < slow
            if bullish and not self._in_position:
                self._in_position = True
                decision = SignalDecision("ENTER_LONG", stop_distance=stop, reason="sma_cross_up")
            elif bearish and self._in_position:
                self._in_position = False
                self._cooldown_left = self.params.cooldown
                decision = SignalDecision("EXIT_LONG", reason="sma_cross_down")

        self._prev_fast, self._prev_slow = fast, slow
        return decision
