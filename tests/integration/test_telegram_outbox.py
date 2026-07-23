"""Telegram outbox delivery retry / dead-letter / restart replay."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from autotrade.core.notify.dispatch import drain_outbox
from autotrade.core.notify.outbox import OutboxService
from autotrade.core.notify.telegram_transport import FakeTelegramSender, TelegramTransport
from autotrade.persistence.models import AuditEvent, NotifyOutbox


@pytest.mark.d1a
def test_telegram_outbox_retry_and_dead_letter(migrated_uow) -> None:  # noqa: ANN001
    outbox = OutboxService(max_attempts=3)
    with migrated_uow.session() as session:
        outbox.enqueue(
            session,
            payload={"text": "[PAPER] account=paper1\ntest", "mode": "PAPER"},
        )
        session.add(
            AuditEvent(
                event_id="src-keep",
                type="fill",
                payload_redacted={"x": 1},
                at=datetime.now(UTC),
                correlation_id=None,
            )
        )

    # Transient then success
    sender = FakeTelegramSender(fail_transient_times=1)
    transport = TelegramTransport(sender=sender, chat_id="chat1")
    stats1 = drain_outbox(migrated_uow, transport, outbox)
    assert stats1["retry"] == 1
    # Force next_attempt due
    with migrated_uow.session() as session:
        row = session.query(NotifyOutbox).one()
        row.next_attempt = datetime.now(UTC)
    stats2 = drain_outbox(migrated_uow, transport, outbox)
    assert stats2["sent"] == 1
    assert sender.messages

    # Permanent 4xx dead-letter; source audit retained
    with migrated_uow.session() as session:
        outbox.enqueue(session, payload={"text": "boom", "mode": "PAPER"})
    bad = FakeTelegramSender(fail_permanent=True)
    drain_outbox(migrated_uow, TelegramTransport(sender=bad, chat_id="chat1"), outbox)
    with migrated_uow.session() as session:
        dead = session.query(NotifyOutbox).filter(NotifyOutbox.dead_letter.is_(True)).count()
        assert dead >= 1
        assert session.get(AuditEvent, "src-keep") is not None


@pytest.mark.d1a
def test_test_message(migrated_uow) -> None:  # noqa: ANN001
    _ = migrated_uow
    sender = FakeTelegramSender()
    transport = TelegramTransport(sender=sender, chat_id="chat1")
    assert transport.send_test_message()["ok"] is True
    assert "test message" in sender.messages[0]["text"]
