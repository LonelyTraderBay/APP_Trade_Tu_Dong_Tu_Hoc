"""T051 — History read model + redacted CSV export, Qt-free.

Source table: `audit_events` (`AuditEvent`). This is the natural single
source for a unified "history" feed — it is where D1a/D1b code already
writes `type`/`correlation_id`/`payload_redacted` for every event this
screen needs to show: intent lifecycle (`intent_reserved`, `intent_unknown`
— see `core/oms/submit.py`, which also embeds `client_order_id` in the
redacted payload), Broker Hub connection tests
(`ui.broker_hub.test_connection`), tray Pause (`ui.tray.pause_l1`), manual
Flatten (`ui.kill_switch.flatten`), and Telegram command rejections
(`telegram_command_rejected`). `OrderIntent`/`Fill` have no `type`/
`correlation_id`/redacted-payload shape of their own and are already fully
covered by the Live Monitor screen (T041) — folding them into History too
would just duplicate that table with a different filter UI, so this stays a
single `AuditEvent` query rather than a three-table union.

`AuditEvent.payload_redacted` is already redacted at write time everywhere
above — this module never re-redacts it, and never reaches into any other
(non-redacted) column or table for extra fields. `client_order_id` has no
dedicated `audit_events` column, so it is filtered by reading the value
already present inside `payload_redacted` (itself redacted at write time,
so this is not a raw-field read).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from autotrade.persistence.models import AuditEvent


@dataclass(frozen=True, slots=True)
class HistoryFilter:
    """All filters optional — an empty filter returns the full (redacted) log."""

    type: str | None = None
    correlation_id: str | None = None
    client_order_id: str | None = None
    since: datetime | None = None
    until: datetime | None = None


@dataclass(frozen=True, slots=True)
class HistoryRow:
    """One redacted audit-log row for the History table/CSV export."""

    event_id: str
    type: str
    at: datetime
    correlation_id: str | None
    client_order_id: str | None
    payload_redacted: dict[str, Any] | None


#: CSV column order — also the only fields ever written to the export file.
CSV_FIELDS: tuple[str, ...] = (
    "event_id",
    "type",
    "at",
    "correlation_id",
    "client_order_id",
    "payload_redacted",
)


def parse_iso_datetime(text: str) -> datetime:
    """Parse a user-typed ISO date/time. Naive input is assumed UTC.

    Raises `ValueError` on malformed input — callers (the view) turn that
    into a warning dialog rather than letting it propagate further.
    """
    value = datetime.fromisoformat(text.strip())
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value


def query_history(session: Session, filt: HistoryFilter) -> list[HistoryRow]:
    """Redacted, filtered audit-log read. No mutation, no raw payload access."""
    stmt = select(AuditEvent)
    if filt.type:
        stmt = stmt.where(AuditEvent.type == filt.type)
    if filt.correlation_id:
        stmt = stmt.where(AuditEvent.correlation_id == filt.correlation_id)
    if filt.since is not None:
        stmt = stmt.where(AuditEvent.at >= filt.since)
    if filt.until is not None:
        stmt = stmt.where(AuditEvent.at <= filt.until)
    stmt = stmt.order_by(AuditEvent.at.desc())

    rows: list[HistoryRow] = []
    for event in session.scalars(stmt).all():
        payload = event.payload_redacted or {}
        client_order_id = payload.get("client_order_id")
        if filt.client_order_id and client_order_id != filt.client_order_id:
            continue
        rows.append(
            HistoryRow(
                event_id=event.event_id,
                type=event.type,
                at=event.at,
                correlation_id=event.correlation_id,
                client_order_id=client_order_id,
                payload_redacted=payload,
            )
        )
    return rows


def export_history_csv(rows: list[HistoryRow], path: Path) -> None:
    """Write `rows` to `path` as CSV. Only already-redacted fields are used —
    this never re-fetches raw payloads or touches the database."""
    import csv
    import json

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_FIELDS)
        for row in rows:
            writer.writerow(
                [
                    row.event_id,
                    row.type,
                    row.at.isoformat(),
                    row.correlation_id or "",
                    row.client_order_id or "",
                    json.dumps(row.payload_redacted) if row.payload_redacted else "",
                ]
            )
