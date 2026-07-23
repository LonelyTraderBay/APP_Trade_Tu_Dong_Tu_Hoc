"""Dispatch pending outbox rows through Telegram transport."""

from __future__ import annotations

from autotrade.core.notify.outbox import OutboxService
from autotrade.core.notify.telegram_transport import (
    PermanentTelegramError,
    TelegramTransport,
    TransientTelegramError,
)
from autotrade.persistence.uow import UnitOfWork


def drain_outbox(
    uow: UnitOfWork,
    transport: TelegramTransport,
    outbox: OutboxService | None = None,
) -> dict[str, int]:
    service = outbox or OutboxService()
    stats = {"sent": 0, "retry": 0, "dead": 0}
    with uow.session() as session:
        for row in service.pending(session):
            text = str((row.payload_redacted or {}).get("text", row.payload_redacted))
            try:
                transport.send(text)
                service.mark_sent(row)
                stats["sent"] += 1
            except TransientTelegramError:
                service.mark_transient_failure(row)
                stats["retry"] += 1
            except PermanentTelegramError:
                service.mark_permanent_4xx(row)
                stats["dead"] += 1
    return stats
