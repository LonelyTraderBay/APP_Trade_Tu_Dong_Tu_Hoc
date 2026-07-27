"""Cancel timeout + late fill -> CANCEL_UNKNOWN; late fill still ingested.

Was previously tautological: it never called `cancel_order` at all — it set
a local variable to `IntentState.CANCEL_UNKNOWN.value` and asserted it
equals itself, proving nothing. This now drives the real `cancel_intent`
(`core/oms/cancel.py`) through the exact fault path it exists to cover,
using the same injection technique `test_timeout_unknown.py` uses against
`DurableSubmitter` (swap the adapter method for one that raises), adapted
to `cancel_order`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from autotrade.core.adapters.paper import PaperAdapter
from autotrade.core.domain.money import d
from autotrade.core.ledger.fills import ingest_fill
from autotrade.core.oms.account_state import AccountGate
from autotrade.core.oms.cancel import cancel_intent
from autotrade.core.oms.fsm import IntentState
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest
from autotrade.core.risk.engine import RiskEngine
from autotrade.persistence.models import AuditEvent, Order, OrderIntent
from autotrade.persistence.uow import UnitOfWork


def _acknowledged_intent(
    uow: UnitOfWork, adapter: PaperAdapter, gate: AccountGate, risk: RiskEngine
) -> tuple[str, str]:
    """Drive an intent to ACKNOWLEDGED — the only state `cancel_intent` is
    legal from, per the FSM. Reuses `test_timeout_unknown.py`'s
    `simulate_timeout_after_send` + `resolve_unknown` path, with a partial
    fill injected so the order resolves to *open* (ACKNOWLEDGED) rather
    than FILLED — that's what gives `cancel_intent` something legal to act
    on, and what sets `Order.broker_order_id` it needs.
    """
    adapter.inject_partial_qty = d("0.5")
    submitter = DurableSubmitter(
        uow=uow, adapter=adapter, risk=risk, gate=gate, simulate_timeout_after_send=True
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
    assert result.intent_id is not None
    assert result.client_order_id is not None
    with uow.session() as session:
        intent = session.get(OrderIntent, result.intent_id)
        assert intent is not None
        assert intent.state == IntentState.ACKNOWLEDGED.value
        order_row = session.query(Order).filter(Order.intent_id == result.intent_id).one()
        assert order_row.broker_order_id is not None
    return result.intent_id, result.client_order_id


@pytest.mark.d1a
def test_cancel_unknown_late_fill(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
    intent_id, client_order_id = _acknowledged_intent(uow, adapter, gate, risk)

    calls = {"n": 0}

    def disconnected_cancel(**kwargs):  # noqa: ANN003
        calls["n"] += 1
        raise RuntimeError("cancel_disconnect")

    adapter.cancel_order = disconnected_cancel  # type: ignore[method-assign]

    result = cancel_intent(uow, adapter, intent_id=intent_id)

    # --- Cancel-side fault: adapter raised AFTER being called ->
    # CANCEL_UNKNOWN, never retried, never silently lost.
    assert result.ok is False
    assert result.state == IntentState.CANCEL_UNKNOWN.value
    assert calls["n"] == 1  # cancel attempted exactly once — no blind retry

    with uow.session() as session:
        intent = session.get(OrderIntent, intent_id)
        assert intent is not None
        assert intent.state == IntentState.CANCEL_UNKNOWN.value
        order_row = session.query(Order).filter(Order.intent_id == intent_id).one()
        assert order_row.state == IntentState.CANCEL_UNKNOWN.value
        audit_types = {
            row.type
            for row in session.query(AuditEvent).filter(
                AuditEvent.correlation_id == intent_id
            )
        }
        assert "intent_cancel_requested" in audit_types
        assert "intent_cancel_unknown" in audit_types

    # --- Late-fill half: a fill for this order arrives (the broker's own
    # fill notification racing our in-flight, now-unknown cancel) while the
    # intent still sits in CANCEL_UNKNOWN. `ingest_fill` is keyed purely by
    # (account_id, broker_execution_id) — it must accept this gracefully
    # without raising, and it must NOT silently "resolve" the intent out of
    # CANCEL_UNKNOWN; that has to stay an explicit query/recon decision,
    # never an implicit side effect of ledger ingestion.
    with uow.session() as session:
        _, created = ingest_fill(
            session,
            account_id="paper1",
            broker_execution_id=f"late-{client_order_id}",
            qty=d("0.5"),
            price=d("100.01"),
            fee=d("0.01"),
            ts=datetime.now(UTC),
        )
        assert created is True

        # Duplicate delivery of the same execution (e.g. recon overlap
        # re-sending it) must not double-count.
        _, created_again = ingest_fill(
            session,
            account_id="paper1",
            broker_execution_id=f"late-{client_order_id}",
            qty=d("0.5"),
            price=d("100.01"),
            fee=d("0.01"),
            ts=datetime.now(UTC),
        )
        assert created_again is False

        intent = session.get(OrderIntent, intent_id)
        assert intent is not None
        assert intent.state == IntentState.CANCEL_UNKNOWN.value
