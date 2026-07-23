"""Lifecycle evidence — only source=real_testnet counts toward ≥50."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from autotrade.core.certify import records as cert_records
from autotrade.persistence.models import LifecycleEvidence

ALLOWED_SOURCE = "real_testnet"


def record_completed_lifecycle(
    session: Session,
    *,
    account_id: str,
    source: str,
    entry_intent_id: str | None = None,
    exit_intent_id: str | None = None,
    notes: str | None = None,
) -> LifecycleEvidence | None:
    """Persist a DONE round-trip. Mock/inject sources are ignored (return None)."""
    if source != ALLOWED_SOURCE:
        return None
    ev = LifecycleEvidence(
        account_id=account_id,
        source=source,
        entry_intent_id=entry_intent_id,
        exit_intent_id=exit_intent_id,
        completed_at=datetime.now(UTC),
        notes=notes,
    )
    session.add(ev)
    session.flush()
    count = count_real_lifecycles(session, account_id=account_id)
    cert_records.set_lifecycle_count(session, count)
    return ev


def count_real_lifecycles(session: Session, *, account_id: str | None = None) -> int:
    stmt = select(func.count()).select_from(LifecycleEvidence).where(
        LifecycleEvidence.source == ALLOWED_SOURCE
    )
    if account_id is not None:
        stmt = stmt.where(LifecycleEvidence.account_id == account_id)
    return int(session.scalar(stmt) or 0)
