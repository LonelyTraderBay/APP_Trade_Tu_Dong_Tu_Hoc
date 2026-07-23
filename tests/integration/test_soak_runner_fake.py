"""Fake soak runner smoke — short duration, no cert promotion."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.certify import records as cert
from autotrade.core.certify.real_soak import run_soak
from autotrade.core.certify.soak import SOAK_REQUIRED


@pytest.mark.d1b
def test_short_soak_does_not_write_cert(migrated_uow) -> None:  # noqa: ANN001
    adapter = CcxtDemoAdapter(exchange=FakeCcxtExchange(), endpoint="binance_spot_testnet")
    adapter.connect()
    clock = {"t": datetime.now(UTC)}

    def now_fn() -> datetime:
        return clock["t"]

    def sleep_fn(seconds: float) -> None:
        clock["t"] = clock["t"] + timedelta(seconds=seconds)

    result = run_soak(
        uow=migrated_uow,
        adapter=adapter,
        account_id="demo1",
        hours=0.0001,
        heartbeat_seconds=0.01,
        write_cert=False,
        sleep_fn=sleep_fn,
        now_fn=now_fn,
    )
    assert result.passed is True
    with migrated_uow.session() as session:
        row = cert.get_cert(session)
        assert row is None or row.soak_passed is False


@pytest.mark.d1b
def test_full_duration_backdated_via_controller_promotes_soak(migrated_uow) -> None:  # noqa: ANN001
    """Controller backdate path (unit) remains the cert soak mark; runner uses same complete()."""
    with migrated_uow.session() as session:
        from autotrade.core.certify.soak import SoakController

        ctl = SoakController(session=session, account_id="demo1")
        run = ctl.start()
        run.started_at = datetime.now(UTC) - SOAK_REQUIRED - timedelta(seconds=1)
        session.add(run)
        done = ctl.complete(run.soak_id, unresolved_recon=0)
        assert done.passed is True
        row = cert.ensure_cert_row(session)
        assert row.soak_passed is True
