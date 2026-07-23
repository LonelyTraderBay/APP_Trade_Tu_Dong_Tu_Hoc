"""Inbound Telegram commands: /status /pnl /pause only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.persistence.models import AuditEvent, TelegramUpdate

ALLOWED = frozenset({"/status", "/pnl", "/pause"})
COMMAND_TTL_SECONDS = 60


@dataclass(frozen=True, slots=True)
class InboundCommand:
    update_id: int
    chat_id: str
    user_id: str
    text: str
    message_date: datetime


@dataclass
class CommandHandler:
    owner_chat_id: str
    owner_user_id: str
    ks: KillSwitch

    def handle(self, session: Session, cmd: InboundCommand) -> dict[str, Any]:
        session.flush()
        existing = session.get(TelegramUpdate, cmd.update_id)
        if existing is not None:
            return {"ok": False, "reason": "duplicate_update_id"}

        accepted = True
        reason = "ok"
        if cmd.chat_id != self.owner_chat_id or cmd.user_id != self.owner_user_id:
            accepted = False
            reason = "wrong_chat_or_user"
        age = (datetime.now(UTC) - cmd.message_date).total_seconds()
        if accepted and age > COMMAND_TTL_SECONDS:
            accepted = False
            reason = "ttl_exceeded"

        text = (cmd.text or "").strip().split()[0] if cmd.text else ""
        if accepted and text not in ALLOWED:
            accepted = False
            reason = "command_not_allowed"

        session.add(
            TelegramUpdate(update_id=cmd.update_id, accepted=accepted, reason=reason)
        )
        session.flush()
        if not accepted:
            session.add(
                AuditEvent(
                    event_id=f"tg-reject-{cmd.update_id}",
                    type="telegram_command_rejected",
                    payload_redacted={
                        "update_id": cmd.update_id,
                        "reason": reason,
                        "text": text,
                    },
                    at=datetime.now(UTC),
                    correlation_id=None,
                )
            )
            return {"ok": False, "reason": reason}

        if text == "/pause":
            self.ks.pause_l1(reason="telegram_pause")
            self.ks.persist(session)
            return {"ok": True, "action": "pause_l1", "ks_level": self.ks.level}
        if text == "/status":
            return {"ok": True, "action": "status", "ks_level": self.ks.level}
        if text == "/pnl":
            return {"ok": True, "action": "pnl"}
        return {"ok": False, "reason": "unreachable"}
