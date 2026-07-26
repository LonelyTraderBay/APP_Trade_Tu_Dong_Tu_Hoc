"""Real-testnet soak harness — skipped unless AUTOTRADE_D1B_REAL=1."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

from autotrade.core.certify.real_lifecycles import build_real_adapter
from autotrade.core.certify.real_soak import abort_soak, run_soak
from autotrade.core.certify.soak import SOAK_REQUIRED, SoakController

# datetime helpers used by REAL smoke advancing clock


@pytest.mark.d1b
@pytest.mark.skipif(os.environ.get("AUTOTRADE_D1B_REAL") != "1", reason="real DEMO only")
def test_demo_soak_real_smoke_connect_abort(migrated_uow) -> None:  # noqa: ANN001
    """REAL smoke: connect + start short soak + abort (does not wait 72h; no cert write)."""
    adapter = build_real_adapter(account_id="demo-binance")
    adapter.connect()
    assert adapter.connected

    # Start a soak row then abort immediately — proves CLI path without 72h wait
    with migrated_uow.session() as session:
        ctl = SoakController(session=session, account_id="demo-binance")
        run = ctl.start()
        soak_id = run.soak_id

    aborted = abort_soak(migrated_uow, soak_id)
    assert aborted.owner_paused is True
    assert aborted.passed is False

    clock = {"t": datetime.now(UTC)}

    def now_fn() -> datetime:
        return clock["t"]

    def sleep_fn(seconds: float) -> None:
        clock["t"] = clock["t"] + timedelta(seconds=seconds)

    # Short non-cert soak loop (write_cert=False) — does not wait wall 72h / no cert write
    result = run_soak(
        uow=migrated_uow,
        adapter=adapter,
        account_id="demo-binance",
        hours=0.0001,
        heartbeat_seconds=0.01,
        write_cert=False,
        sleep_fn=sleep_fn,
        now_fn=now_fn,
    )
    assert result.passed is True
    assert result.message == "ok"


@pytest.mark.d1b
def test_soak_controller_pause_fails(migrated_uow) -> None:  # noqa: ANN001
    with migrated_uow.session() as session:
        ctl = SoakController(session=session, account_id="demo1")
        run = ctl.start()
        ctl.mark_owner_pause(run.soak_id)
        done = ctl.complete(run.soak_id, unresolved_recon=0)
        assert done.passed is False


@pytest.mark.d1b
def test_soak_controller_pass_wall_clock(migrated_uow) -> None:  # noqa: ANN001
    with migrated_uow.session() as session:
        ctl = SoakController(session=session, account_id="demo1")
        run = ctl.start()
        # Backdate start to satisfy 72h without sleeping
        run.started_at = datetime.now(UTC) - SOAK_REQUIRED - timedelta(minutes=1)
        session.add(run)
        done = ctl.complete(run.soak_id, unresolved_recon=0)
        assert done.passed is True


@pytest.mark.d1b
def test_soak_controller_complete_naive_started_at(migrated_uow) -> None:  # noqa: ANN001
    """SQLite may return naive UTC — complete must not TypeError (V8 orphan root cause)."""
    with migrated_uow.session() as session:
        ctl = SoakController(session=session, account_id="demo1")
        run = ctl.start()
        run.started_at = (datetime.now(UTC) - SOAK_REQUIRED - timedelta(minutes=1)).replace(
            tzinfo=None
        )
        session.add(run)
        done = ctl.complete(run.soak_id, unresolved_recon=0, now=datetime.now(UTC))
        assert done.passed is True
        assert done.ended_at is not None
