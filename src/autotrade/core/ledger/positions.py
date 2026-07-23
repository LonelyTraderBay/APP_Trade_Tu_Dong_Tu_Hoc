"""positions_local derived view + provenance."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from autotrade.persistence.models import PositionLocal


def upsert_position_local(
    session: Session,
    *,
    account_id: str,
    symbol: str,
    qty: Decimal,
    provenance: dict | None = None,
) -> PositionLocal:
    row = (
        session.query(PositionLocal)
        .filter(
            PositionLocal.account_id == account_id,
            PositionLocal.symbol == symbol,
        )
        .one_or_none()
    )
    if row is None:
        row = PositionLocal(
            account_id=account_id,
            symbol=symbol,
            qty=qty,
            provenance=provenance,
        )
        session.add(row)
    else:
        row.qty = qty
        row.provenance = provenance
    session.flush()
    return row
