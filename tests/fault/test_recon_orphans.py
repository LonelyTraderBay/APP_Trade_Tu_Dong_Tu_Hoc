"""Orphan recon: broker wins exposure; history intact; L2."""

from __future__ import annotations

import pytest

from autotrade.core.domain.money import d
from autotrade.core.ledger.recon import reconcile
from autotrade.core.oms.account_state import AccountStatus
from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.persistence.models import AuditEvent, OrderIntent, ReconBreak


@pytest.mark.d1a
def test_recon_orphans(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
    _ = risk
    # Broker has orphan position with no local intents
    adapter._positions["PAPER-INTERNAL-1"] = d("2")
    with uow.session() as session:
        session.add(
            AuditEvent(
                event_id="audit-keep",
                type="seed",
                payload_redacted={"keep": True},
                at=__import__("datetime").datetime.now(
                    __import__("datetime").UTC
                ),
                correlation_id=None,
            )
        )

    ks = KillSwitch(scope="account:paper1")
    out = reconcile(uow=uow, adapter=adapter, gate=gate, ks=ks, account_id="paper1")
    assert out["breaks"]
    assert ks.level >= 2
    assert gate.status == AccountStatus.SAFE_LOCK
    with uow.session() as session:
        assert session.query(ReconBreak).count() >= 1
        assert session.get(AuditEvent, "audit-keep") is not None
        assert session.query(OrderIntent).count() == 0  # history not fabricated/deleted
