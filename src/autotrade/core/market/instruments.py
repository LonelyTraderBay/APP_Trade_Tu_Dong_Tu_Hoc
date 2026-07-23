"""Synthetic Paper instruments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from autotrade.core.domain.money import d

PAPER_INTERNAL_1 = "PAPER-INTERNAL-1"


@dataclass(frozen=True, slots=True)
class Instrument:
    internal_symbol: str
    tick_size: Decimal
    lot_size: Decimal
    updated_at: datetime
    ttl_seconds: int = 3600


def paper_internal_1(*, now: datetime | None = None) -> Instrument:
    return Instrument(
        internal_symbol=PAPER_INTERNAL_1,
        tick_size=d("0.01"),
        lot_size=d("0.001"),
        updated_at=now or datetime.now(UTC),
    )
