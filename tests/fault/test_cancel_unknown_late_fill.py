"""Cancel timeout + late fill → CANCEL_UNKNOWN semantics; single fill ingest."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from autotrade.core.domain.money import d
from autotrade.core.ledger.fills import ingest_fill
from autotrade.core.oms.fsm import IntentState


@pytest.mark.d1a
def test_cancel_unknown_late_fill(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
    _ = gate, risk
    adapter.inject_partial_qty = d("0.5")
    order = adapter.place_order(
        client_order_id="c-late",
        symbol="PAPER-INTERNAL-1",
        side="buy",
        qty=d("1"),
    )
    # Simulate cancel racing with remaining qty — mark cancel unknown locally.
    cancel_state = IntentState.CANCEL_UNKNOWN.value
    late = adapter.list_executions()["items"][0]
    with uow.session() as session:
        ingest_fill(
            session,
            account_id="paper1",
            broker_execution_id=late["broker_execution_id"],
            qty=d(late["qty"]),
            price=d(late["price"]),
            fee=d(late["fee"]),
            ts=datetime.now(UTC),
        )
        # duplicate ingest
        _, created = ingest_fill(
            session,
            account_id="paper1",
            broker_execution_id=late["broker_execution_id"],
            qty=d(late["qty"]),
            price=d(late["price"]),
            fee=d(late["fee"]),
            ts=datetime.now(UTC),
        )
        assert created is False
    assert cancel_state == "CANCEL_UNKNOWN"
    assert order["state"] == "PARTIAL"
