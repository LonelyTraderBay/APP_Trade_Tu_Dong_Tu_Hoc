"""UNKNOWN path: hold reservation, query by client_id, never blind re-place."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from autotrade.core.adapters.protocol import BrokerAdapter
from autotrade.core.domain.money import d
from autotrade.core.ledger.fills import ingest_fill
from autotrade.core.oms.fsm import DeliveryCertainty, IntentState
from autotrade.core.risk.engine import RiskEngine
from autotrade.persistence.models import Order, OrderIntent, RiskReservation
from autotrade.persistence.uow import UnitOfWork


def resolve_unknown(
    uow: UnitOfWork,
    adapter: BrokerAdapter,
    risk: RiskEngine,
    *,
    intent_id: str,
    client_order_id: str,
    reservation_id: str,
    account_id: str,
) -> dict[str, Any]:
    """Query broker by client id. MUST NOT call place_order again."""
    found = adapter.query_order_by_client_id(client_order_id)
    with uow.session() as session:
        intent = session.get(OrderIntent, intent_id)
        order_row = session.query(Order).filter(Order.intent_id == intent_id).one()
        reservation = session.get(RiskReservation, reservation_id)

        if found is None:
            # Still uncertain / not visible — keep hold
            if intent is not None:
                intent.state = IntentState.UNKNOWN.value
            order_row.delivery_certainty = DeliveryCertainty.MAY_HAVE_BEEN_ACCEPTED.value
            return {"state": "UNKNOWN", "held": True}

        if intent is not None:
            intent.state = (
                IntentState.FILLED.value
                if found.get("state") == "FILLED"
                else IntentState.ACKNOWLEDGED.value
            )
        order_row.state = intent.state if intent is not None else found.get("state")
        order_row.broker_order_id = found.get("broker_order_id")
        order_row.delivery_certainty = DeliveryCertainty.CONFIRMED.value

        for item in adapter.list_executions()["items"]:
            if item["client_order_id"] == client_order_id:
                ingest_fill(
                    session,
                    account_id=account_id,
                    broker_execution_id=item["broker_execution_id"],
                    qty=d(item["qty"]),
                    price=d(item["price"]),
                    fee=d(item["fee"]),
                    ts=datetime.now(UTC),
                )
        if reservation is not None:
            reservation.state = "CONSUMED"
        risk.release(reservation_id)
        return found
