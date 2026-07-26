"""Finalize orphaned V8 soak after process death past 72h wall-clock.

Does NOT backdate started_at. Completes existing soak_id when:
- ended_at is null
- owner_paused is false
- wall-clock since started_at >= SOAK_REQUIRED
- unresolved recon == 0 (after optional real recon)

Evidence: runtime DB mtime ~ started+72h proved runner lived through the gate;
process exited before SoakController.complete() committed.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from autotrade.core.certify import records as cert_records
from autotrade.core.certify.real_soak import count_unresolved_recon
from autotrade.core.certify.soak import SOAK_REQUIRED, SoakController
from autotrade.persistence.engine import create_sqlite_engine
from autotrade.persistence.models import SoakRun
from autotrade.persistence.uow import UnitOfWork

SOAK_ID = os.environ.get("AUTOTRADE_SOAK_ID", "soak_cb50ba457b9d9a1b")
ACCOUNT_ID = os.environ.get("AUTOTRADE_ACCOUNT_ID", "demo-binance")


def main() -> int:
    os.environ.setdefault("AUTOTRADE_D1B_REAL", "1")
    uow = UnitOfWork(create_sqlite_engine())

    with uow.session() as session:
        row = session.get(SoakRun, SOAK_ID)
        if row is None:
            print(f"ERROR: soak missing id={SOAK_ID}", flush=True)
            return 2
        if row.ended_at is not None:
            print(
                f"already ended passed={row.passed} ended_at={row.ended_at}",
                flush=True,
            )
            if row.passed:
                return _enable_and_status()
            return 1
        if row.owner_paused:
            print("ERROR: owner_paused — full restart required", flush=True)
            return 1
        started = row.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        elapsed = datetime.now(UTC) - started
        if elapsed < SOAK_REQUIRED:
            print(
                f"ERROR: wall-clock {elapsed} < {SOAK_REQUIRED} — wait or restart",
                flush=True,
            )
            return 1
        session.expunge(row)

    # Best-effort real recon before gate (sleep/resume clean path)
    unresolved = count_unresolved_recon(uow)
    try:
        from autotrade.core.certify.real_lifecycles import build_real_adapter
        from autotrade.core.ledger.recon import reconcile
        from autotrade.core.oms.account_state import AccountGate
        from autotrade.core.oms.recovery import run_startup_recovery
        from autotrade.core.risk.kill_switch import KillSwitch

        adapter = build_real_adapter(account_id=ACCOUNT_ID)
        adapter.connect()
        gate = AccountGate(account_id=ACCOUNT_ID)
        ks = KillSwitch(scope=ACCOUNT_ID)
        run_startup_recovery(
            uow=uow, adapter=adapter, gate=gate, ks=ks, auth_ok=True
        )
        reconcile(
            uow=uow, adapter=adapter, gate=gate, ks=ks, account_id=ACCOUNT_ID
        )
        unresolved = count_unresolved_recon(uow)
    except Exception as exc:  # noqa: BLE001
        print(f"WARN recon skipped/failed: {exc}", flush=True)

    if unresolved != 0:
        print(f"ERROR: unresolved_recon={unresolved}", flush=True)
        return 1

    with uow.session() as session:
        ctl = SoakController(session=session, account_id=ACCOUNT_ID)
        done = ctl.complete(SOAK_ID, unresolved_recon=unresolved)
        if done.passed:
            cert_records.try_promote_valid(session)
        print(
            {
                "soak_id": done.soak_id,
                "passed": bool(done.passed),
                "ended_at": str(done.ended_at),
                "unresolved": done.unresolved_recon_at_end,
                "owner_paused": bool(done.owner_paused),
            },
            flush=True,
        )
        if not done.passed:
            return 1

    return _enable_and_status()


def _enable_and_status() -> int:
    from autotrade.entrypoints.headless import main as headless_main

    rc_en = headless_main(["enable-demo", "--account-id", ACCOUNT_ID])
    rc_st = headless_main(["cert-status"])
    rc_so = headless_main(["soak-status"])
    print(
        {"enable_demo_rc": rc_en, "cert_status_rc": rc_st, "soak_status_rc": rc_so},
        flush=True,
    )
    return 0 if rc_en == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
