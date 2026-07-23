"""Cert gates must block enable-demo until contract+fault+lifecycle+soak promote valid."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from autotrade.core.accounts.active import get_active_account
from autotrade.core.accounts.bindings import bind_demo_strategy
from autotrade.core.certify import records as cert
from autotrade.core.certify.lifecycle import record_completed_lifecycle
from autotrade.core.certify.records import CertificationNotValid, assert_cert_valid_for_trading
from autotrade.core.certify.soak import SOAK_REQUIRED, SoakController
from autotrade.core.oms.account_state import AccountStatus
from autotrade.persistence.models import Account


def _try_enable(session, account_id: str = "demo-binance") -> None:  # noqa: ANN001
    assert_cert_valid_for_trading(session)
    acc = session.get(Account, account_id)
    if acc is None:
        acc = Account(
            account_id=account_id,
            adapter_id="ccxt",
            mode="DEMO",
            endpoint="binance_spot_testnet",
            status=AccountStatus.READY.value,
            eligibility="DEMO_CERTIFIED",
            is_active=False,
        )
        session.add(acc)
        session.flush()
    else:
        acc.status = AccountStatus.READY.value
        acc.eligibility = "DEMO_CERTIFIED"
    bind_demo_strategy(session, account_id=account_id)
    from autotrade.core.accounts.active import switch_active_account

    switch_active_account(session, target_account_id=account_id, position_qty=0.0)


@pytest.mark.d1b
def test_enable_demo_refuses_without_soak(migrated_uow) -> None:  # noqa: ANN001
    with migrated_uow.session() as session:
        cert.mark_contract_passed(session)
        cert.mark_fault_passed(session)
        for i in range(50):
            record_completed_lifecycle(
                session,
                account_id="demo-binance",
                source="real_testnet",
                notes=f"n={i}",
            )
        row = cert.try_promote_valid(session)
        assert row.valid is False
        with pytest.raises(CertificationNotValid):
            _try_enable(session)


@pytest.mark.d1b
def test_enable_demo_allows_when_all_gates(migrated_uow) -> None:  # noqa: ANN001
    with migrated_uow.session() as session:
        cert.mark_contract_passed(session)
        cert.mark_fault_passed(session)
        for i in range(50):
            record_completed_lifecycle(
                session,
                account_id="demo-binance",
                source="real_testnet",
                notes=f"n={i}",
            )
        ctl = SoakController(session=session, account_id="demo-binance")
        run = ctl.start()
        run.started_at = datetime.now(UTC) - SOAK_REQUIRED - timedelta(minutes=1)
        session.add(run)
        done = ctl.complete(run.soak_id, unresolved_recon=0)
        assert done.passed is True
        row = cert.try_promote_valid(session)
        assert row.valid is True
        _try_enable(session)
        session.flush()
        active = get_active_account(session)
        assert active is not None
        assert active.account_id == "demo-binance"
        assert active.mode == "DEMO"
        assert active.is_active is True
