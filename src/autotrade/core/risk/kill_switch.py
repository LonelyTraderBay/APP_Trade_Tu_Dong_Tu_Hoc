"""Kill-switch L1–L4 with durable persistence helper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from autotrade.persistence.models import KillSwitchState


@dataclass
class KillSwitch:
    scope: str
    level: int = 0
    latched: bool = False
    triggers: dict[str, Any] | None = None

    def raise_to(self, level: int, *, reason: str) -> None:
        if level < 1 or level > 4:
            raise ValueError("KS level must be 1..4")
        if level < self.level:
            return  # never auto-downgrade via raise_to
        self.level = level
        self.latched = True
        self.triggers = {"reason": reason, "level": level}

    def pause_l1(self, *, reason: str = "pause") -> None:
        self.raise_to(1, reason=reason)

    def persist(self, session: Session) -> None:
        row = (
            session.query(KillSwitchState)
            .filter(KillSwitchState.scope == self.scope)
            .one_or_none()
        )
        if row is None:
            row = KillSwitchState(
                scope=self.scope,
                level=self.level,
                triggers_json=self.triggers,
                latched=self.latched,
            )
            session.add(row)
        else:
            # Never auto-lower on persist/load path.
            row.level = max(row.level, self.level)
            self.level = row.level
            row.latched = True if row.level > 0 else self.latched
            row.triggers_json = self.triggers
            self.latched = row.latched

    @classmethod
    def load(cls, session: Session, scope: str) -> KillSwitch:
        row = (
            session.query(KillSwitchState)
            .filter(KillSwitchState.scope == scope)
            .one_or_none()
        )
        if row is None:
            return cls(scope=scope)
        return cls(
            scope=scope,
            level=row.level,
            latched=row.latched,
            triggers=row.triggers_json,
        )
