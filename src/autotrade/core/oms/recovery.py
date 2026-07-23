"""Startup Recovery checklist for Paper (§11.2 subset)."""

from __future__ import annotations

from dataclasses import dataclass

from autotrade.core.adapters.protocol import BrokerAdapter
from autotrade.core.oms.account_state import AccountGate, AccountStatus
from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.persistence.uow import UnitOfWork


@dataclass
class RecoveryResult:
    ready: bool
    status: AccountStatus
    reasons: list[str]


def run_startup_recovery(
    *,
    uow: UnitOfWork,
    adapter: BrokerAdapter,
    gate: AccountGate,
    ks: KillSwitch,
    auth_ok: bool = True,
    pagination_complete: bool = True,
    data_fresh: bool = True,
    unresolved_breaks: bool = False,
) -> RecoveryResult:
    gate.begin_recovery()
    reasons: list[str] = []

    # Restore KS first — never auto-lower.
    with uow.session() as session:
        loaded = KillSwitch.load(session, ks.scope)
        ks.level = max(ks.level, loaded.level)
        ks.latched = ks.level > 0 or loaded.latched
        ks.persist(session)

    if not auth_ok:
        reasons.append("auth_fail")
        try:
            adapter.connect()
        except Exception:  # noqa: BLE001
            pass
        if not adapter.connected:
            reasons.append("connect_fail")

    if not adapter.connected and auth_ok:
        try:
            adapter.connect()
        except Exception as exc:  # noqa: BLE001
            reasons.append(f"connect_fail:{exc}")

    if not pagination_complete:
        reasons.append("pagination_incomplete")
    else:
        page = adapter.list_open_orders(page=1, page_size=100)
        if not page.get("done", True):
            reasons.append("pagination_incomplete")

    if not data_fresh:
        reasons.append("stale_data")
    if unresolved_breaks:
        reasons.append("unresolved_breaks")

    if reasons:
        for r in reasons:
            gate.lock(r)
        return RecoveryResult(ready=False, status=gate.status, reasons=list(gate.reasons))

    gate.mark_ready()
    return RecoveryResult(ready=True, status=gate.status, reasons=[])
