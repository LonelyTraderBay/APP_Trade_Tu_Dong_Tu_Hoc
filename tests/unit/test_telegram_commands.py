"""Telegram command allowlist / TTL / dedup tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from autotrade.core.notify.commands import CommandHandler, InboundCommand
from autotrade.core.risk.kill_switch import KillSwitch


@pytest.mark.d1a
def test_telegram_commands(migrated_uow) -> None:  # noqa: ANN001
    ks = KillSwitch(scope="account:paper1")
    handler = CommandHandler(owner_chat_id="chat1", owner_user_id="user1", ks=ks)
    now = datetime.now(UTC)

    with migrated_uow.session() as session:
        ok = handler.handle(
            session,
            InboundCommand(1, "chat1", "user1", "/pause", now),
        )
        assert ok["ok"] is True
        assert ks.level == 1

        dup = handler.handle(
            session,
            InboundCommand(1, "chat1", "user1", "/pause", now),
        )
        assert dup["reason"] == "duplicate_update_id"

        wrong = handler.handle(
            session,
            InboundCommand(2, "other", "user1", "/status", now),
        )
        assert wrong["reason"] == "wrong_chat_or_user"

        stale = handler.handle(
            session,
            InboundCommand(
                3, "chat1", "user1", "/pnl", now - timedelta(seconds=120)
            ),
        )
        assert stale["reason"] == "ttl_exceeded"

        bad = handler.handle(
            session,
            InboundCommand(4, "chat1", "user1", "/flatten", now),
        )
        assert bad["reason"] == "command_not_allowed"

        whitespace = handler.handle(
            session,
            InboundCommand(5, "chat1", "user1", "   ", now),
        )
        assert whitespace["ok"] is False
        assert whitespace["reason"] == "command_not_allowed"
