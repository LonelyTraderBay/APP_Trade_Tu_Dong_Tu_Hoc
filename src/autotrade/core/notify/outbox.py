"""Durable notify outbox — delivery retry/backoff/dead-letter (not OMS retry)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from autotrade.core.domain.ids import IdFactory
from autotrade.persistence.models import NotifyOutbox


@dataclass
class OutboxService:
    ids: IdFactory | None = None
    max_attempts: int = 5

    def __post_init__(self) -> None:
        if self.ids is None:
            self.ids = IdFactory()

    def enqueue(
        self,
        session: Session,
        *,
        payload: dict[str, Any],
        channel: str = "telegram",
    ) -> str:
        event_id = self.ids.uuid4()  # type: ignore[union-attr]
        session.add(
            NotifyOutbox(
                event_id=event_id,
                channel=channel,
                status="pending",
                attempts=0,
                next_attempt=datetime.now(UTC),
                dead_letter=False,
                payload_redacted=payload,
            )
        )
        return event_id

    def pending(self, session: Session) -> list[NotifyOutbox]:
        now = datetime.now(UTC)
        return (
            session.query(NotifyOutbox)
            .filter(
                NotifyOutbox.dead_letter.is_(False),
                NotifyOutbox.status.in_(("pending", "retry")),
                or_(
                    NotifyOutbox.next_attempt.is_(None),
                    NotifyOutbox.next_attempt <= now,
                ),
            )
            .all()
        )

    def mark_sent(self, row: NotifyOutbox) -> None:
        row.status = "sent"
        row.next_attempt = None

    def mark_transient_failure(self, row: NotifyOutbox) -> None:
        row.attempts += 1
        row.status = "retry"
        row.next_attempt = datetime.now(UTC) + timedelta(seconds=2**row.attempts)
        if row.attempts >= self.max_attempts:
            row.dead_letter = True
            row.status = "dead"

    def mark_permanent_4xx(self, row: NotifyOutbox) -> None:
        row.attempts += 1
        row.dead_letter = True
        row.status = "dead"
