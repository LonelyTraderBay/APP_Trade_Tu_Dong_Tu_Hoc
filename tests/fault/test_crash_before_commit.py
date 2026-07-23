"""Crash before intent commit → no broker request."""

from __future__ import annotations

import pytest

from autotrade.core.domain.money import d
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest
from autotrade.persistence.models import OrderIntent, RiskReservation


@pytest.mark.d1a
def test_crash_before_commit(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
    submitter = DurableSubmitter(
        uow=uow, adapter=adapter, risk=risk, gate=gate, fail_commit=True
    )
    submitter.submit(
        SubmitRequest(
            account_id="paper1",
            symbol="PAPER-INTERNAL-1",
            side="buy",
            qty=d("1"),
            price=d("100"),
        )
    )
    with uow.session() as session:
        assert session.query(OrderIntent).count() == 0
        assert session.query(RiskReservation).count() == 0
    assert adapter.query_order_by_client_id("anything") is None
    assert adapter.get_positions() == []
