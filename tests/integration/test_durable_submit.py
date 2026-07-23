"""Integration: durable submit + Paper fill."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from autotrade.core.domain.money import d
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest
from autotrade.persistence.models import (
    AuditEvent,
    BalanceSnapshot,
    ExecutionCursor,
    OrderIntent,
    RiskReservation,
    Signal,
)


@pytest.mark.d1a
def test_durable_submit_paper_fill(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
    submitter = DurableSubmitter(uow=uow, adapter=adapter, risk=risk, gate=gate)
    result = submitter.submit(
        SubmitRequest(
            account_id="paper1",
            symbol="PAPER-INTERNAL-1",
            side="buy",
            qty=d("1"),
            price=d("100"),
            stop_price=d("95"),
            emit_notify=True,
            signal_id="sig-1",
        )
    )
    assert result.ok is True
    assert result.adapter_called is True
    with uow.session() as session:
        intent = session.get(OrderIntent, result.intent_id)
        assert intent is not None
        assert intent.state == "FILLED"
        assert session.scalar(select(AuditEvent).limit(1)) is not None
        assert session.get(Signal, "sig-1") is not None
        assert session.scalar(select(BalanceSnapshot).limit(1)) is not None
        assert session.get(ExecutionCursor, "paper1") is not None
        reservation = session.get(RiskReservation, intent.reservation_id)
        assert reservation is not None
        assert reservation.state == "CONSUMED"
