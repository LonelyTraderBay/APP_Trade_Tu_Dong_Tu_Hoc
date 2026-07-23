"""Idempotent fill ledger."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from autotrade.persistence.models import Fill


def ingest_fill(
    session: Session,
    *,
    account_id: str,
    broker_execution_id: str,
    qty: Decimal,
    price: Decimal,
    fee: Decimal,
    ts: datetime | None = None,
) -> tuple[Fill, bool]:
    """Return (fill, created). Duplicate broker_execution_id → created=False."""
    existing = (
        session.query(Fill)
        .filter(
            Fill.account_id == account_id,
            Fill.broker_execution_id == broker_execution_id,
        )
        .one_or_none()
    )
    if existing is not None:
        return existing, False
    row = Fill(
        account_id=account_id,
        broker_execution_id=broker_execution_id,
        qty=qty,
        price=price,
        fee=fee,
        ts=ts or datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row, True
