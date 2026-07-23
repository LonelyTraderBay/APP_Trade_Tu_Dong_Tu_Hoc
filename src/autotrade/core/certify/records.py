"""Certification record load/save/invalidate (DEMO trading requires valid=True)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.persistence.models import CertificationRecord

LIFECYCLE_GATE = 50


class CertificationNotValid(RuntimeError):
    """DEMO trading READY refused — certification missing or invalid."""


def get_cert(session: Session, tuple_key: str | None = None) -> CertificationRecord | None:
    key = tuple_key or D1B_ALLOWLIST.canonical_key
    return session.query(CertificationRecord).filter_by(tuple_key=key).one_or_none()


def _cert_id_for(tuple_key: str) -> str:
    return "cert-" + tuple_key.replace("|", "-")[:48]


def ensure_cert_row(session: Session) -> CertificationRecord:
    key = D1B_ALLOWLIST.canonical_key
    row = session.query(CertificationRecord).filter_by(tuple_key=key).one_or_none()
    if row is None:
        row = CertificationRecord(
            cert_id=_cert_id_for(key),
            tuple_key=key,
            valid=False,
            lifecycle_count=0,
            soak_passed=False,
        )
        session.add(row)
        session.flush()
    return row


def mark_contract_passed(session: Session, *, at: datetime | None = None) -> CertificationRecord:
    row = ensure_cert_row(session)
    row.contract_suite_passed_at = at or datetime.now(UTC)
    session.add(row)
    return row


def mark_fault_passed(session: Session, *, at: datetime | None = None) -> CertificationRecord:
    row = ensure_cert_row(session)
    row.fault_suite_passed_at = at or datetime.now(UTC)
    session.add(row)
    return row


def set_lifecycle_count(
    session: Session, count: int, *, at: datetime | None = None
) -> CertificationRecord:
    row = ensure_cert_row(session)
    row.lifecycle_count = count
    if count >= LIFECYCLE_GATE:
        row.lifecycle_passed_at = at or datetime.now(UTC)
    session.add(row)
    return row


def mark_soak_passed(
    session: Session,
    *,
    started_at: datetime,
    ended_at: datetime,
) -> CertificationRecord:
    row = ensure_cert_row(session)
    row.soak_started_at = started_at
    row.soak_ended_at = ended_at
    row.soak_passed = True
    session.add(row)
    return row


def try_promote_valid(session: Session) -> CertificationRecord:
    """Set valid=True only when contract+fault+lifecycle≥50+soak all recorded."""
    row = ensure_cert_row(session)
    session.flush()
    ok = (
        row.contract_suite_passed_at is not None
        and row.fault_suite_passed_at is not None
        and int(row.lifecycle_count or 0) >= LIFECYCLE_GATE
        and row.lifecycle_passed_at is not None
        and bool(row.soak_passed)
    )
    row.valid = bool(ok)
    if not ok:
        row.invalidated_reason = row.invalidated_reason or "gates_incomplete"
    else:
        row.invalidated_reason = None
    session.add(row)
    session.flush()
    return row


def assert_cert_valid_for_trading(session: Session) -> CertificationRecord:
    row = get_cert(session)
    if row is None or not row.valid:
        raise CertificationNotValid("DEMO trading requires valid certification record")
    return row


def invalidate(
    session: Session,
    *,
    reason: str,
    endpoint_fingerprint: str | None = None,
    instrument_metadata_hash: str | None = None,
    ccxt_version: str | None = None,
    app_version: str | None = None,
) -> CertificationRecord:
    row = ensure_cert_row(session)
    row.valid = False
    row.invalidated_reason = reason
    if endpoint_fingerprint is not None:
        row.endpoint_fingerprint = endpoint_fingerprint
    if instrument_metadata_hash is not None:
        row.instrument_metadata_hash = instrument_metadata_hash
    if ccxt_version is not None:
        row.ccxt_version = ccxt_version
    if app_version is not None:
        row.app_version = app_version
    session.add(row)
    return row


def snapshot_versions(
    session: Session,
    *,
    app_version: str,
    ccxt_version: str,
    endpoint_fingerprint: str,
    instrument_metadata_hash: str,
    capability: dict[str, Any] | None = None,
) -> CertificationRecord:
    row = ensure_cert_row(session)
    row.app_version = app_version
    row.ccxt_version = ccxt_version
    row.endpoint_fingerprint = endpoint_fingerprint
    row.instrument_metadata_hash = instrument_metadata_hash
    row.capability_snapshot_json = capability
    session.add(row)
    return row
