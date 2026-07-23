"""Decimal money/quantity helpers — never binary float for risk math."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

type Money = Decimal
type Qty = Decimal


def d(value: str | int | Decimal) -> Decimal:
    """Parse to Decimal; reject float to avoid binary rounding traps."""
    if isinstance(value, float):
        raise TypeError("float is forbidden for money/qty; use str or Decimal")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid decimal: {value!r}") from exc


def quantize(value: Decimal, places: str = "0.00000001") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)
