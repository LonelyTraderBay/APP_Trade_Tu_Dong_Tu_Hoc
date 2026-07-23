"""Account READY / SAFE_LOCK / RECOVERING gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AccountStatus(StrEnum):
    NEW = "NEW"
    RECOVERING = "RECOVERING"
    READY = "READY"
    SAFE_LOCK = "SAFE_LOCK"


@dataclass
class AccountGate:
    account_id: str
    status: AccountStatus = AccountStatus.NEW
    reasons: list[str] = field(default_factory=list)

    def begin_recovery(self) -> None:
        self.status = AccountStatus.RECOVERING
        self.reasons = []

    def lock(self, reason: str) -> None:
        self.status = AccountStatus.SAFE_LOCK
        self.reasons.append(reason)

    def mark_ready(self) -> None:
        if self.status == AccountStatus.SAFE_LOCK:
            raise RuntimeError("cannot READY while SAFE_LOCK")
        self.status = AccountStatus.READY
        self.reasons = []

    @property
    def allows_exposure_increase(self) -> bool:
        return self.status == AccountStatus.READY
