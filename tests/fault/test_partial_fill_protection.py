"""Partial fill during protection → qty sync or lock."""

from __future__ import annotations

import pytest

from autotrade.core.domain.money import d
from autotrade.core.oms.account_state import AccountGate
from autotrade.core.oms.protection import sync_protection
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest


@pytest.mark.d1a
def test_partial_fill_protection(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
    adapter.inject_partial_qty = d("0.4")
    submitter = DurableSubmitter(uow=uow, adapter=adapter, risk=risk, gate=gate)
    result = submitter.submit(
        SubmitRequest(
            account_id="paper1",
            symbol="PAPER-INTERNAL-1",
            side="buy",
            qty=d("1"),
            price=d("100"),
            stop_price=d("95"),
        )
    )
    assert result.ok is True
    assert result.order is not None
    assert result.order["state"] == "PARTIAL"
    prot = sync_protection(
        adapter,
        gate,
        client_order_id=result.client_order_id or "",
        symbol="PAPER-INTERNAL-1",
        filled_qty=d(result.order["filled_qty"]),
        stop_price=d("95"),
    )
    assert prot.ok is True
    assert prot.qty == d("0.4")

    adapter.fail_protection = True
    gate2 = AccountGate("paper1")
    gate2.mark_ready()
    bad = sync_protection(
        adapter,
        gate2,
        client_order_id="x",
        symbol="PAPER-INTERNAL-1",
        filled_qty=d("0.4"),
        stop_price=d("95"),
    )
    assert bad.escalate_lock is True
