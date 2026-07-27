"""Post-audit fix — `run_desktop_startup_recovery` (FR-004), Qt-free.

Mirrors `tests/unit/test_broker_hub_controller.py`'s pattern: pure
`migrated_uow` fixture, `FakeCcxtExchange` injected via `exchange_factory`,
never touches real network/ccxt/keyring.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from autotrade.app_ui.services.startup import run_desktop_startup_recovery
from autotrade.core.adapters.ccxt_demo.adapter import FakeCcxtExchange
from autotrade.core.oms.account_state import AccountStatus
from autotrade.persistence.models import Account, ReconBreak
from autotrade.persistence.uow import UnitOfWork

DEMO_ACCOUNT_ID = "demo-binance"
PAPER_ACCOUNT_ID = "paper1"


def _seed_paper_active(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add(
            Account(
                account_id=PAPER_ACCOUNT_ID,
                adapter_id="paper",
                mode="PAPER",
                status="READY",
                eligibility="PAPER",
                is_active=True,
            )
        )


def _seed_demo_active(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add(
            Account(
                account_id=DEMO_ACCOUNT_ID,
                adapter_id="ccxt",
                mode="DEMO",
                endpoint="binance_spot_testnet",
                status="READY",
                eligibility="DEMO_CERTIFIED",
                is_active=True,
            )
        )


@pytest.mark.d1c
def test_no_active_account_returns_none(migrated_uow: UnitOfWork) -> None:
    result = run_desktop_startup_recovery(migrated_uow)

    assert result is None


@pytest.mark.d1c
def test_unmigrated_db_returns_none_without_raising(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    # No `alembic upgrade` ran: the accounts table does not exist yet. This
    # must degrade the same way `--check`'s existing banner catch does, not
    # propagate an OperationalError out of the entrypoint.
    from autotrade.persistence.engine import create_sqlite_engine

    data_dir = tmp_path / "empty"
    data_dir.mkdir()
    monkeypatch.setenv("AUTOTRADE_DATA_DIR", str(data_dir))
    uow = UnitOfWork(create_sqlite_engine(data_dir / "autotrade.sqlite3"))

    result = run_desktop_startup_recovery(uow)

    assert result is None


@pytest.mark.d1c
def test_active_paper_account_with_healthy_adapter_is_ready(
    migrated_uow: UnitOfWork,
) -> None:
    _seed_paper_active(migrated_uow)

    result = run_desktop_startup_recovery(migrated_uow)

    assert result is not None
    assert result.ready is True
    assert result.status == AccountStatus.READY
    assert result.reasons == []


@pytest.mark.d1c
def test_active_demo_account_with_healthy_adapter_is_ready(
    migrated_uow: UnitOfWork,
) -> None:
    _seed_demo_active(migrated_uow)

    result = run_desktop_startup_recovery(
        migrated_uow, exchange_factory=FakeCcxtExchange
    )

    assert result is not None
    assert result.ready is True
    assert result.status == AccountStatus.READY


@pytest.mark.d1c
def test_adapter_connect_failure_locks_with_connect_fail_reason(
    migrated_uow: UnitOfWork,
) -> None:
    _seed_demo_active(migrated_uow)

    result = run_desktop_startup_recovery(
        migrated_uow,
        exchange_factory=lambda: FakeCcxtExchange(fail_auth=True),
    )

    assert result is not None
    assert result.ready is False
    assert result.status == AccountStatus.SAFE_LOCK
    assert any("connect_fail" in reason for reason in result.reasons)


@pytest.mark.d1c
def test_open_recon_breaks_lock_with_unresolved_breaks_reason(
    migrated_uow: UnitOfWork,
) -> None:
    _seed_paper_active(migrated_uow)
    with migrated_uow.session() as session:
        session.add(
            ReconBreak(
                type="orphan",
                payload={"account_id": PAPER_ACCOUNT_ID},
                status="OPEN",
                at=datetime.now(UTC),
            )
        )

    result = run_desktop_startup_recovery(migrated_uow)

    assert result is not None
    assert result.ready is False
    assert result.status == AccountStatus.SAFE_LOCK
    assert "unresolved_breaks" in result.reasons


@pytest.mark.d1c
def test_never_raises_when_adapter_cannot_be_built(migrated_uow: UnitOfWork) -> None:
    # An account row with an unsupported adapter_id (defensive: schema
    # doesn't constrain this column) must fold into a locked result, not an
    # unhandled exception reaching the entrypoint.
    with migrated_uow.session() as session:
        session.add(
            Account(
                account_id="broken1",
                adapter_id="not_a_real_adapter",
                mode="PAPER",
                status="READY",
                eligibility="PAPER",
                is_active=True,
            )
        )

    result = run_desktop_startup_recovery(migrated_uow)  # must not raise

    assert result is not None
    assert result.ready is False
    assert result.status == AccountStatus.SAFE_LOCK
    assert any("connect_fail" in reason for reason in result.reasons)
