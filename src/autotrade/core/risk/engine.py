"""Fail-closed risk check + atomic reservation (in-memory/DB-ready)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from autotrade.core.domain.ids import IdFactory
from autotrade.core.domain.money import d


@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_notional: Decimal = d("10000")
    max_qty: Decimal = d("10")


@dataclass(frozen=True, slots=True)
class RiskDecision:
    risk_check_id: str
    approved: bool
    reasons: tuple[str, ...]
    reservation_id: str | None = None


class RiskEngine:
    def __init__(self, limits: RiskLimits | None = None, ids: IdFactory | None = None) -> None:
        self.limits = limits or RiskLimits()
        self.ids = ids or IdFactory()
        self._held: dict[str, Decimal] = {}

    def check_increase(
        self,
        *,
        account_id: str,
        qty: Decimal,
        price: Decimal,
        ks_level: int = 0,
    ) -> RiskDecision:
        check_id = self.ids.uuid4()
        reasons: list[str] = []
        if ks_level >= 1:
            reasons.append("kill_switch_blocks_entry")
        notional = qty * price
        if qty > self.limits.max_qty:
            reasons.append("qty_limit")
        if notional > self.limits.max_notional:
            reasons.append("notional_limit")
        if reasons:
            return RiskDecision(check_id, False, tuple(reasons))

        reservation_id = self.ids.uuid4()
        self._held[reservation_id] = qty
        return RiskDecision(check_id, True, (), reservation_id=reservation_id)

    def release(self, reservation_id: str) -> None:
        self._held.pop(reservation_id, None)

    def is_held(self, reservation_id: str) -> bool:
        return reservation_id in self._held
