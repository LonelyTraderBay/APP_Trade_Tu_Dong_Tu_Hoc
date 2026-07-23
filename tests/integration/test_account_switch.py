"""Paper ↔ DEMO account switch."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from autotrade.core.accounts.active import SwitchRejected, switch_active_account
from autotrade.core.oms.fsm import IntentState
from autotrade.persistence.models import Account, OrderIntent, ReconBreak


@pytest.mark.d1b
def test_switch_paper_demo_when_flat(migrated_uow) -> None:  # noqa: ANN001
    with migrated_uow.session() as session:
        paper = Account(
            account_id="paper1",
            adapter_id="paper",
            mode="PAPER",
            status="READY",
            eligibility="PAPER",
            is_active=True,
        )
        demo = Account(
            account_id="demo1",
            adapter_id="ccxt",
            mode="DEMO",
            endpoint="binance_spot_testnet",
            status="READY",
            eligibility="DEMO_CERTIFIED",
            is_active=False,
        )
        session.add_all([paper, demo])
        session.flush()
        switch_active_account(session, target_account_id="demo1", position_qty=0.0)
        assert session.get(Account, "demo1").is_active is True
        assert session.get(Account, "paper1").is_active is False


@pytest.mark.d1b
def test_switch_refused_when_not_flat(migrated_uow) -> None:  # noqa: ANN001
    with migrated_uow.session() as session:
        session.add(
            Account(
                account_id="paper1",
                adapter_id="paper",
                mode="PAPER",
                status="READY",
                eligibility="PAPER",
                is_active=True,
            )
        )
        session.add(
            Account(
                account_id="demo1",
                adapter_id="ccxt",
                mode="DEMO",
                status="READY",
                eligibility="DEMO",
                is_active=False,
            )
        )
        session.flush()
        with pytest.raises(SwitchRejected, match="not_flat"):
            switch_active_account(session, target_account_id="demo1", position_qty=1.0)


@pytest.mark.d1b
def test_switch_refused_open_recon(migrated_uow) -> None:  # noqa: ANN001
    with migrated_uow.session() as session:
        session.add(
            Account(
                account_id="paper1",
                adapter_id="paper",
                mode="PAPER",
                status="READY",
                eligibility="PAPER",
                is_active=True,
            )
        )
        session.add(
            Account(
                account_id="demo1",
                adapter_id="ccxt",
                mode="DEMO",
                status="READY",
                eligibility="DEMO",
                is_active=False,
            )
        )
        session.flush()
        session.add(
            ReconBreak(
                type="orphan",
                payload={"account_id": "paper1"},
                status="open",
                at=datetime.now(UTC),
            )
        )
        session.flush()
        with pytest.raises(SwitchRejected, match="open_recon"):
            switch_active_account(session, target_account_id="demo1", position_qty=0.0)


@pytest.mark.d1b
def test_switch_refused_unknown_intent(migrated_uow) -> None:  # noqa: ANN001
    with migrated_uow.session() as session:
        session.add(
            Account(
                account_id="paper1",
                adapter_id="paper",
                mode="PAPER",
                status="READY",
                eligibility="PAPER",
                is_active=True,
            )
        )
        session.add(
            Account(
                account_id="demo1",
                adapter_id="ccxt",
                mode="DEMO",
                status="READY",
                eligibility="DEMO",
                is_active=False,
            )
        )
        session.add(
            OrderIntent(
                intent_id="i1",
                client_order_id="c1",
                state=IntentState.UNKNOWN.value,
                account_id="paper1",
                side="buy",
                qty=1,
                symbol="PAPER-INTERNAL-1",
            )
        )
        session.flush()
        with pytest.raises(SwitchRejected, match="unknown"):
            switch_active_account(session, target_account_id="demo1", position_qty=0.0)
