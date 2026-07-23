"""Crash after commit before send → NOT_SENT; no blind retry."""

from __future__ import annotations

import pytest

from autotrade.core.domain.money import d
from autotrade.core.oms.fsm import DeliveryCertainty
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest
from autotrade.persistence.models import Order, OrderIntent


@pytest.mark.d1a
def test_crash_after_commit_not_sent(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper

    def boom() -> None:
        raise RuntimeError("crash_before_send")

    submitter = DurableSubmitter(
        uow=uow,
        adapter=adapter,
        risk=risk,
        gate=gate,
        on_before_adapter=boom,
    )
    result = submitter.submit(
        SubmitRequest(
            account_id="paper1",
            symbol="PAPER-INTERNAL-1",
            side="buy",
            qty=d("1"),
            price=d("100"),
        )
    )
    assert result.adapter_called is False
    assert result.delivery == DeliveryCertainty.NOT_SENT.value
    with uow.session() as session:
        intent = session.get(OrderIntent, result.intent_id)
        assert intent is not None  # committed
        order = session.query(Order).filter(Order.intent_id == result.intent_id).one()
        assert order.delivery_certainty == DeliveryCertainty.NOT_SENT.value
    # Must not have placed on broker
    assert result.client_order_id is not None
    assert adapter.query_order_by_client_id(result.client_order_id) is None
