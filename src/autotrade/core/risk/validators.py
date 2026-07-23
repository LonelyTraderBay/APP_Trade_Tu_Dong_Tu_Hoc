"""Reduce-only / no-position-flip safety validator."""

from __future__ import annotations

from decimal import Decimal


def validate_reduce_only(
    *,
    side: str,
    qty: Decimal,
    position_qty: Decimal,
) -> tuple[bool, str]:
    """Allow exits that reduce exposure; reject flips that would reverse through zero."""
    if position_qty == 0:
        return False, "no_position"
    if side.lower() == "sell" and position_qty > 0:
        if qty > position_qty:
            return False, "would_flip"
        return True, "ok"
    if side.lower() == "buy" and position_qty < 0:
        if qty > abs(position_qty):
            return False, "would_flip"
        return True, "ok"
    return False, "not_reducing"
