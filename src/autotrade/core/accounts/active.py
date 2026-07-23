"""Single active account switch (Paper XOR DEMO)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from autotrade.core.oms.fsm import IntentState
from autotrade.persistence.models import Account, OrderIntent, ReconBreak


class SwitchRejected(RuntimeError):
    """Account switch refused fail-closed."""


class ActiveMode(StrEnum):
    PAPER = "PAPER"
    DEMO = "DEMO"


@dataclass(frozen=True, slots=True)
class SwitchPreconditions:
    flat: bool
    no_open_recon: bool
    no_unknown: bool

    @property
    def ok(self) -> bool:
        return self.flat and self.no_open_recon and self.no_unknown


def evaluate_preconditions(
    session: Session,
    *,
    account_id: str,
    position_qty: float = 0.0,
) -> SwitchPreconditions:
    open_recons = session.scalars(
        select(ReconBreak).where(
            ReconBreak.status.in_(["OPEN", "UNRESOLVED", "open", "unresolved"])
        )
    ).all()
    open_recon = None
    for br in open_recons:
        payload = br.payload or {}
        if payload.get("account_id") in (None, account_id):
            open_recon = br
            break
    unknown = session.scalars(
        select(OrderIntent).where(
            OrderIntent.account_id == account_id,
            OrderIntent.state.in_(
                [
                    IntentState.UNKNOWN.value,
                    IntentState.SUBMITTING.value,
                ]
            ),
        )
    ).first()
    return SwitchPreconditions(
        flat=abs(position_qty) < 1e-12,
        no_open_recon=open_recon is None,
        no_unknown=unknown is None,
    )


def get_active_account(session: Session) -> Account | None:
    return session.scalars(select(Account).where(Account.is_active.is_(True))).first()


def switch_active_account(
    session: Session,
    *,
    target_account_id: str,
    position_qty: float = 0.0,
) -> Account:
    current = get_active_account(session)
    target = session.get(Account, target_account_id)
    if target is None:
        raise SwitchRejected(f"unknown account: {target_account_id}")
    if target.mode not in {"PAPER", "DEMO"}:
        raise SwitchRejected("LIVE accounts not allowed in D1b")
    if target.mode == "DEMO" and target.adapter_id != "ccxt":
        raise SwitchRejected("DEMO account must use ccxt adapter")

    check_id = current.account_id if current is not None else target_account_id
    pre = evaluate_preconditions(session, account_id=check_id, position_qty=position_qty)
    if not pre.ok:
        reasons = []
        if not pre.flat:
            reasons.append("not_flat")
        if not pre.no_open_recon:
            reasons.append("open_recon")
        if not pre.no_unknown:
            reasons.append("unknown_or_submitting")
        raise SwitchRejected(",".join(reasons))

    session.execute(update(Account).values(is_active=False))
    target.is_active = True
    session.add(target)
    return target
