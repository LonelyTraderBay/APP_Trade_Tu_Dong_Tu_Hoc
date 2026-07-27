"""T011 — tray actions, Qt-free.

Contract (`contracts/ui-core-boundary.md`): tray **Pause is never gated by
PIN** and must always be available — a lockout must not be able to trap the
operator with a running strategy. Resume / risk-raising stays PIN-gated and
deliberately lives elsewhere.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Protocol
from uuid import uuid4

from sqlalchemy.orm import Session

from autotrade.app_ui.services.dashboard import DashboardSnapshot, build_dashboard_snapshot
from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.persistence.models import AuditEvent
from autotrade.persistence.uow import UnitOfWork

DEFAULT_KS_SCOPE = "global"
PAUSE_AUDIT_TYPE = "ui.tray.pause_l1"

#: Money columns are Numeric(24, 12), so a raw Decimal renders as
#: "1123.500000000000". Note `:g` does NOT help here: unlike float, Decimal
#: formatting honours the value's own exponent. Quantise for display instead.
_MONEY_PLACES = Decimal("0.01")


def format_money(value: Decimal | None, *, signed: bool = False) -> str:
    """Render a money amount for the UI: 2 decimals, em-dash when unknown."""
    if value is None:
        return "—"
    quantised = value.quantize(_MONEY_PLACES, rounding=ROUND_HALF_EVEN)
    return f"{quantised:+f}" if signed else f"{quantised:f}"


class KillSwitchPort(Protocol):
    """Minimum surface the tray needs — lets tests inject a fake."""

    level: int
    latched: bool

    def pause_l1(self, *, reason: str = ...) -> None: ...

    def persist(self, session: Session) -> None: ...


KillSwitchLoader = Callable[[Session, str], KillSwitchPort]


@dataclass(frozen=True, slots=True)
class PauseResult:
    """Outcome of a tray Pause, for the toast the view shows afterwards."""

    level: int
    latched: bool
    already_paused: bool

    @property
    def message(self) -> str:
        if self.already_paused:
            return f"Already paused — kill-switch stays at L{self.level}."
        return f"Paused — kill-switch raised to L{self.level}."


class TrayController:
    """Bridges tray menu actions to core commands.

    `kill_switch_loader` defaults to the real persistent kill-switch; unit
    tests pass a fake to prove no PIN check sits on this path.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        *,
        scope: str = DEFAULT_KS_SCOPE,
        kill_switch_loader: KillSwitchLoader | None = None,
        adapter_connected: Callable[[], bool] | None = None,
    ) -> None:
        self._uow = uow
        self._scope = scope
        self._load_ks: KillSwitchLoader = kill_switch_loader or KillSwitch.load
        self._adapter_connected = adapter_connected or (lambda: False)

    @property
    def uow(self) -> UnitOfWork:
        """Exposed so sibling controllers (e.g. BrokerHubController) can share
        the same UnitOfWork instead of the view constructing its own."""
        return self._uow

    def pause(self, *, reason: str = "tray_pause") -> PauseResult:
        """Raise the kill-switch to at least L1. No PIN, ever. Idempotent."""
        with self._uow.session() as session:
            ks = self._load_ks(session, self._scope)
            already = ks.level >= 1
            ks.pause_l1(reason=reason)
            ks.persist(session)
            session.add(
                AuditEvent(
                    event_id=uuid4().hex,
                    type=PAUSE_AUDIT_TYPE,
                    payload_redacted={
                        "scope": self._scope,
                        "reason": reason,
                        "level": ks.level,
                        "already_paused": already,
                    },
                    at=datetime.now(UTC),
                )
            )
            return PauseResult(
                level=ks.level,
                latched=ks.latched,
                already_paused=already,
            )

    def snapshot(self, *, now: datetime | None = None) -> DashboardSnapshot:
        """Read-only projection for the tray tooltip and the Dashboard."""
        with self._uow.session() as session:
            return build_dashboard_snapshot(
                session,
                now=now,
                adapter_connected=self._adapter_connected(),
                ks_scope=self._scope,
            )

    def tooltip(self, *, now: datetime | None = None) -> str:
        snap = self.snapshot(now=now)
        return (
            f"AutoTrade AI · {snap.account.banner}\n"
            f"Equity {format_money(snap.equity)} · "
            f"PnL {format_money(snap.pnl_day, signed=True)} · "
            f"KS L{snap.ks_level} · {snap.recovery_status}"
        )
