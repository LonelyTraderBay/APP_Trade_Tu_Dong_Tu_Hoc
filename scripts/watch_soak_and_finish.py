"""Wait for active D1b soak to finish, then enable-demo + print cert (no secrets).

Run while V8 soak is in progress. Does not backdate or shorten SOAK_REQUIRED.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import UTC, datetime, timedelta

# Ensure package import when run as script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from autotrade.core.certify.records import get_cert
from autotrade.persistence.engine import create_sqlite_engine
from autotrade.persistence.models import SoakRun
from autotrade.persistence.uow import UnitOfWork

SOAK_ID = os.environ.get("AUTOTRADE_SOAK_ID", "soak_cb50ba457b9d9a1b")
ACCOUNT_ID = os.environ.get("AUTOTRADE_ACCOUNT_ID", "demo-binance")
POLL_SEC = float(os.environ.get("AUTOTRADE_SOAK_POLL_SEC", "300"))
START_HINT = datetime.fromisoformat("2026-07-23 07:53:35.649649").replace(tzinfo=UTC)


def _uow() -> UnitOfWork:
    return UnitOfWork(create_sqlite_engine())


def load_soak(uow: UnitOfWork) -> SoakRun | None:
    with uow.session() as session:
        row = session.get(SoakRun, SOAK_ID)
        if row is None:
            return None
        session.expunge(row)
        return row


def main() -> int:
    os.environ.setdefault("AUTOTRADE_D1B_REAL", "1")
    uow = _uow()
    print(f"watcher start soak_id={SOAK_ID} poll={POLL_SEC}s", flush=True)

    while True:
        row = load_soak(uow)
        now = datetime.now(UTC)
        if row is None:
            print("ERROR: soak row missing", flush=True)
            return 2

        started = row.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        elapsed_h = (now - started).total_seconds() / 3600.0
        print(
            f"{now.isoformat()} ended={row.ended_at} passed={row.passed} "
            f"paused={row.owner_paused} elapsed_h={elapsed_h:.2f}",
            flush=True,
        )

        if row.ended_at is not None:
            if row.owner_paused or not row.passed:
                print(
                    f"SOAK_FAILED paused={row.owner_paused} passed={row.passed} "
                    f"— restart full 72h required",
                    flush=True,
                )
                return 1
            break

        # Still running — wait
        time.sleep(POLL_SEC)

    # Promote path already ran inside run_soak; ensure enable-demo
    from autotrade.entrypoints.headless import main as headless_main

    print("soak PASSED — running enable-demo + cert-status", flush=True)
    rc_en = headless_main(["enable-demo", "--account-id", ACCOUNT_ID])
    rc_st = headless_main(["cert-status"])
    with uow.session() as session:
        cert = get_cert(session)
        print(
            {
                "enable_demo_rc": rc_en,
                "cert_status_rc": rc_st,
                "valid": bool(cert.valid) if cert else False,
                "soak_passed": bool(cert.soak_passed) if cert else False,
                "lifecycle_count": int(cert.lifecycle_count or 0) if cert else 0,
            },
            flush=True,
        )
    if rc_en != 0 or not (cert and cert.valid):
        print("POST_SOAK incomplete — check cert gates manually", flush=True)
        return 1
    print("POST_SOAK_OK — update docs/mvp-capability-matrix.md Evidence (Owner/agent)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
