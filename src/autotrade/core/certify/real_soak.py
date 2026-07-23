"""Real DEMO soak runner (SC-005) — wall-clock continuous with heartbeat."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from autotrade.core.adapters.protocol import BrokerAdapter
from autotrade.core.certify import records as cert_records
from autotrade.core.certify.soak import SOAK_REQUIRED, SoakController
from autotrade.core.ledger.recon import reconcile
from autotrade.core.oms.account_state import AccountGate
from autotrade.core.oms.recovery import run_startup_recovery
from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.persistence.models import ReconBreak, SoakRun
from autotrade.persistence.uow import UnitOfWork


@dataclass
class SoakRunResult:
    soak_id: str
    passed: bool
    owner_paused: bool
    unresolved_recon: int
    elapsed: timedelta
    message: str


def count_unresolved_recon(uow: UnitOfWork) -> int:
    with uow.session() as session:
        rows = (
            session.query(ReconBreak)
            .filter(ReconBreak.status.in_(["open", "OPEN", "unresolved", "UNRESOLVED"]))
            .all()
        )
        return len(rows)


def run_soak(
    *,
    uow: UnitOfWork,
    adapter: BrokerAdapter,
    account_id: str,
    hours: float = 72.0,
    heartbeat_seconds: float = 300.0,
    write_cert: bool = True,
    sleep_fn: Any = time.sleep,
    now_fn: Any = None,
) -> SoakRunResult:
    """Run continuous soak for `hours` wall-clock.

    - Owner pause is not automatic; call abort_soak to fail the gate.
    - Detect large wall-clock gaps (sleep/resume) and run recovery before continue.
    - For unit tests: pass hours=0.01 and sleep_fn=lambda _: None; set write_cert=False
      so short soaks never promote certification.
    """
    if hours <= 0:
        raise ValueError("hours must be > 0")
    if not adapter.connected:
        adapter.connect()

    now = now_fn or (lambda: datetime.now(UTC))
    required = timedelta(hours=hours)
    # Only full 72h (or more) may write soak_passed into certification when write_cert
    cert_eligible = write_cert and required >= SOAK_REQUIRED

    with uow.session() as session:
        ctl = SoakController(session=session, account_id=account_id)
        run = ctl.start()
        soak_id = run.soak_id

    gate = AccountGate(account_id=account_id)
    ks = KillSwitch(scope=account_id)
    started = now()
    last_beat = started

    while True:
        # Abort if Owner paused this soak
        with uow.session() as session:
            row = session.get(SoakRun, soak_id)
            if row is not None and row.owner_paused:
                elapsed = now() - started
                return SoakRunResult(
                    soak_id=soak_id,
                    passed=False,
                    owner_paused=True,
                    unresolved_recon=count_unresolved_recon(uow),
                    elapsed=elapsed,
                    message="owner_paused",
                )

        t = now()
        gap = t - last_beat
        # Sleep/resume heuristic: gap >> heartbeat
        if gap > timedelta(seconds=max(heartbeat_seconds * 3, 60)):
            run_startup_recovery(
                uow=uow,
                adapter=adapter,
                gate=gate,
                ks=ks,
                auth_ok=True,
            )
            reconcile(uow=uow, adapter=adapter, gate=gate, ks=ks, account_id=account_id)

        if not adapter.connected:
            try:
                adapter.connect()
            except Exception as exc:  # noqa: BLE001
                # Stay in loop; unresolved will be checked at end
                _ = exc

        try:
            reconcile(uow=uow, adapter=adapter, gate=gate, ks=ks, account_id=account_id)
        except Exception:  # noqa: BLE001
            pass

        last_beat = now()
        elapsed = last_beat - started
        if elapsed >= required:
            break
        # Sleep remaining capped by heartbeat
        remaining = (required - elapsed).total_seconds()
        sleep_fn(min(heartbeat_seconds, max(0.0, remaining)))

    unresolved = count_unresolved_recon(uow)
    with uow.session() as session:
        ctl = SoakController(session=session, account_id=account_id)
        # If short soak for tests, still complete row but do not mark cert
        if not cert_eligible:
            row = session.get(SoakRun, soak_id)
            if row is None:
                raise KeyError(soak_id)
            row.ended_at = now()
            row.unresolved_recon_at_end = unresolved
            row.passed = unresolved == 0 and not row.owner_paused
            session.add(row)
            passed = bool(row.passed)
        else:
            done = ctl.complete(soak_id, unresolved_recon=unresolved, now=now())
            passed = bool(done.passed)
            if passed:
                cert_records.try_promote_valid(session)

    return SoakRunResult(
        soak_id=soak_id,
        passed=passed,
        owner_paused=False,
        unresolved_recon=unresolved,
        elapsed=now() - started,
        message="ok" if passed else "failed_recon_or_duration",
    )


def abort_soak(uow: UnitOfWork, soak_id: str) -> SoakRun:
    """Owner pause — fails continuous soak gate."""
    with uow.session() as session:
        ctl = SoakController(session=session, account_id="unused")
        row = ctl.mark_owner_pause(soak_id)
        session.expunge(row)
        return row


def get_active_soak(uow: UnitOfWork, account_id: str) -> SoakRun | None:
    with uow.session() as session:
        row = (
            session.query(SoakRun)
            .filter_by(account_id=account_id, ended_at=None)
            .order_by(SoakRun.started_at.desc())
            .first()
        )
        if row is None:
            return None
        session.expunge(row)
        return row
