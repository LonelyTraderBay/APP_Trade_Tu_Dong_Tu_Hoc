"""Durable OMS submit: commit intent+reservation+audit before adapter call."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from autotrade.core.adapters.paper import PaperAdapter
from autotrade.core.domain.ids import IdFactory
from autotrade.core.domain.money import d
from autotrade.core.domain.redaction import redact_mapping
from autotrade.core.ledger.fills import ingest_fill
from autotrade.core.ledger.positions import upsert_position_local
from autotrade.core.oms.account_state import AccountGate, AccountStatus
from autotrade.core.oms.fsm import DeliveryCertainty, IntentState
from autotrade.core.oms.protection import sync_protection
from autotrade.core.oms.unknown import resolve_unknown
from autotrade.core.risk.engine import RiskEngine
from autotrade.persistence.models import (
    AuditEvent,
    BalanceSnapshot,
    ExecutionCursor,
    NotifyOutbox,
    Order,
    OrderIntent,
    RiskCheck,
    RiskReservation,
    Signal,
)
from autotrade.persistence.uow import UnitOfWork


class CommitFailed(RuntimeError):
    """Injected or real commit failure — adapter must not be called."""


@dataclass
class SubmitRequest:
    account_id: str
    symbol: str
    side: str
    qty: Decimal
    price: Decimal
    stop_price: Decimal | None = None
    emit_notify: bool = False
    signal_id: str | None = None


@dataclass
class SubmitResult:
    ok: bool
    intent_id: str | None = None
    client_order_id: str | None = None
    state: str | None = None
    delivery: str | None = None
    error: str | None = None
    adapter_called: bool = False
    order: dict[str, Any] | None = None


@dataclass
class DurableSubmitter:
    uow: UnitOfWork
    adapter: PaperAdapter
    risk: RiskEngine
    gate: AccountGate
    ids: IdFactory = field(default_factory=IdFactory)
    # Test hooks
    fail_commit: bool = False
    simulate_timeout_after_send: bool = False
    on_before_adapter: Callable[[], None] | None = None

    def submit(self, req: SubmitRequest) -> SubmitResult:
        if not self.gate.allows_exposure_increase and req.side.lower() == "buy":
            return SubmitResult(ok=False, error="account_not_ready")

        decision = self.risk.check_increase(
            account_id=req.account_id,
            qty=req.qty,
            price=req.price,
            ks_level=0 if self.gate.status == AccountStatus.READY else 1,
        )
        if not decision.approved:
            with self.uow.session() as session:
                session.add(
                    RiskCheck(
                        risk_check_id=decision.risk_check_id,
                        account_id=req.account_id,
                        result="REJECT",
                        reasons_json={"reasons": list(decision.reasons)},
                        at=datetime.now(UTC),
                    )
                )
            return SubmitResult(ok=False, error="risk_reject:" + ",".join(decision.reasons))

        intent_id = self.ids.uuid4()
        client_order_id = self.ids.client_order_id()
        assert decision.reservation_id is not None

        try:
            with self.uow.session() as session:
                self._persist_pre_submit(
                    session,
                    req=req,
                    intent_id=intent_id,
                    client_order_id=client_order_id,
                    risk_check_id=decision.risk_check_id,
                    reservation_id=decision.reservation_id,
                )
                if self.fail_commit:
                    raise CommitFailed("injected commit failure")
        except CommitFailed as exc:
            self.gate.lock("commit_failed")
            self.risk.release(decision.reservation_id)
            return SubmitResult(
                ok=False,
                intent_id=intent_id,
                client_order_id=client_order_id,
                error=str(exc),
                adapter_called=False,
            )
        except Exception:
            self.gate.lock("commit_failed")
            self.risk.release(decision.reservation_id)
            raise

        if self.on_before_adapter is not None:
            try:
                self.on_before_adapter()
            except Exception as exc:  # noqa: BLE001
                with self.uow.session() as session:
                    intent = session.get(OrderIntent, intent_id)
                    order_row = (
                        session.query(Order).filter(Order.intent_id == intent_id).one_or_none()
                    )
                    if intent is not None:
                        intent.state = IntentState.SUBMITTING.value
                    if order_row is not None:
                        order_row.delivery_certainty = DeliveryCertainty.NOT_SENT.value
                        order_row.state = IntentState.SUBMITTING.value
                return SubmitResult(
                    ok=False,
                    intent_id=intent_id,
                    client_order_id=client_order_id,
                    delivery=DeliveryCertainty.NOT_SENT.value,
                    error=str(exc),
                    adapter_called=False,
                )

        # Post-commit: SUBMITTING / SENDING then adapter
        adapter_called = False
        try:
            if not self.adapter.connected:
                raise RuntimeError("adapter_disconnected")
            adapter_called = True
            if self.simulate_timeout_after_send:
                # Mark UNKNOWN without treating response as final — query path only.
                with self.uow.session() as session:
                    self._mark_unknown(
                        session, intent_id=intent_id, client_order_id=client_order_id
                    )
                # Still place once for Paper fault sim of "may have been accepted",
                # then resolve via query — never a second place.
                order = self.adapter.place_order(
                    client_order_id=client_order_id,
                    symbol=req.symbol,
                    side=req.side,
                    qty=req.qty,
                )
                resolved = resolve_unknown(
                    self.uow,
                    self.adapter,
                    self.risk,
                    intent_id=intent_id,
                    client_order_id=client_order_id,
                    reservation_id=decision.reservation_id,
                    account_id=req.account_id,
                )
                return SubmitResult(
                    ok=True,
                    intent_id=intent_id,
                    client_order_id=client_order_id,
                    state=IntentState.FILLED.value
                    if resolved.get("state") == "FILLED"
                    else IntentState.UNKNOWN.value,
                    delivery=DeliveryCertainty.MAY_HAVE_BEEN_ACCEPTED.value,
                    adapter_called=True,
                    order=order,
                )

            order = self.adapter.place_order(
                client_order_id=client_order_id,
                symbol=req.symbol,
                side=req.side,
                qty=req.qty,
            )
            with self.uow.session() as session:
                self._finalize_fill(
                    session,
                    req=req,
                    intent_id=intent_id,
                    client_order_id=client_order_id,
                    reservation_id=decision.reservation_id,
                    order=order,
                )
            return SubmitResult(
                ok=True,
                intent_id=intent_id,
                client_order_id=client_order_id,
                state=IntentState.FILLED.value,
                delivery=DeliveryCertainty.CONFIRMED.value,
                adapter_called=True,
                order=order,
            )
        except Exception as exc:  # noqa: BLE001
            if adapter_called:
                with self.uow.session() as session:
                    self._mark_unknown(
                        session, intent_id=intent_id, client_order_id=client_order_id
                    )
                return SubmitResult(
                    ok=False,
                    intent_id=intent_id,
                    client_order_id=client_order_id,
                    state=IntentState.UNKNOWN.value,
                    delivery=DeliveryCertainty.MAY_HAVE_BEEN_ACCEPTED.value,
                    error=str(exc),
                    adapter_called=True,
                )
            with self.uow.session() as session:
                intent = session.get(OrderIntent, intent_id)
                order_row = (
                    session.query(Order).filter(Order.intent_id == intent_id).one_or_none()
                )
                if intent is not None:
                    intent.state = IntentState.SUBMITTING.value
                if order_row is not None:
                    order_row.delivery_certainty = DeliveryCertainty.NOT_SENT.value
            return SubmitResult(
                ok=False,
                intent_id=intent_id,
                client_order_id=client_order_id,
                delivery=DeliveryCertainty.NOT_SENT.value,
                error=str(exc),
                adapter_called=False,
            )

    def _persist_pre_submit(
        self,
        session: Session,
        *,
        req: SubmitRequest,
        intent_id: str,
        client_order_id: str,
        risk_check_id: str,
        reservation_id: str,
    ) -> None:
        now = datetime.now(UTC)
        session.add(
            RiskCheck(
                risk_check_id=risk_check_id,
                account_id=req.account_id,
                result="APPROVE",
                reasons_json={},
                at=now,
            )
        )
        session.add(
            RiskReservation(
                reservation_id=reservation_id,
                account_id=req.account_id,
                intent_id=intent_id,
                qty=req.qty,
                notional=req.qty * req.price,
                state="HELD",
                at=now,
            )
        )
        session.add(
            OrderIntent(
                intent_id=intent_id,
                client_order_id=client_order_id,
                state=IntentState.RESERVED.value,
                protection_spec={
                    "stop_price": None if req.stop_price is None else str(req.stop_price)
                },
                risk_check_id=risk_check_id,
                reservation_id=reservation_id,
                account_id=req.account_id,
                side=req.side,
                qty=req.qty,
                symbol=req.symbol,
            )
        )
        session.add(
            Order(
                intent_id=intent_id,
                broker_order_id=None,
                delivery_certainty=DeliveryCertainty.NOT_SENT.value,
                state=IntentState.RESERVED.value,
            )
        )
        session.add(
            AuditEvent(
                event_id=self.ids.uuid4(),
                type="intent_reserved",
                payload_redacted=redact_mapping(
                    {
                        "intent_id": intent_id,
                        "client_order_id": client_order_id,
                        "account_id": req.account_id,
                        "side": req.side,
                        "qty": str(req.qty),
                    }
                ),
                at=now,
                correlation_id=intent_id,
            )
        )
        if req.emit_notify:
            session.add(
                NotifyOutbox(
                    event_id=self.ids.uuid4(),
                    channel="telegram",
                    status="pending",
                    attempts=0,
                    next_attempt=now,
                    dead_letter=False,
                    payload_redacted={
                        "mode": "PAPER",
                        "account": req.account_id,
                        "event": "intent_reserved",
                    },
                )
            )
        if req.signal_id:
            session.add(
                Signal(
                    signal_id=req.signal_id,
                    strategy_id="rule_sma_cross_v1",
                    event_time=now,
                    side=req.side,
                    strength=d("1"),
                    feature_snapshot_id=None,
                )
            )
        session.flush()

    def _mark_unknown(
        self, session: Session, *, intent_id: str, client_order_id: str
    ) -> None:
        intent = session.get(OrderIntent, intent_id)
        order_row = session.query(Order).filter(Order.intent_id == intent_id).one()
        if intent is not None:
            intent.state = IntentState.UNKNOWN.value
        order_row.state = IntentState.UNKNOWN.value
        order_row.delivery_certainty = DeliveryCertainty.MAY_HAVE_BEEN_ACCEPTED.value
        session.add(
            AuditEvent(
                event_id=self.ids.uuid4(),
                type="intent_unknown",
                payload_redacted={
                    "intent_id": intent_id,
                    "client_order_id": client_order_id,
                },
                at=datetime.now(UTC),
                correlation_id=intent_id,
            )
        )

    def _finalize_fill(
        self,
        session: Session,
        *,
        req: SubmitRequest,
        intent_id: str,
        client_order_id: str,
        reservation_id: str,
        order: dict[str, Any],
    ) -> None:
        now = datetime.now(UTC)
        intent = session.get(OrderIntent, intent_id)
        order_row = session.query(Order).filter(Order.intent_id == intent_id).one()
        if intent is not None:
            intent.state = IntentState.FILLED.value
        order_row.state = IntentState.FILLED.value
        order_row.broker_order_id = order["broker_order_id"]
        order_row.delivery_certainty = DeliveryCertainty.CONFIRMED.value

        # Paper place_order already created execution id in list — synthesize stable id.
        exec_id = f"local-{client_order_id}"
        for item in self.adapter.list_executions()["items"]:
            if item["client_order_id"] == client_order_id:
                exec_id = item["broker_execution_id"]
                break
        ingest_fill(
            session,
            account_id=req.account_id,
            broker_execution_id=exec_id,
            qty=d(order["filled_qty"]),
            price=d(order["avg_price"]),
            fee=d(order["fee"]),
            ts=now,
        )
        pos_qty = d("0")
        for p in self.adapter.get_positions():
            if p["symbol"] == req.symbol:
                pos_qty = d(p["qty"])
        upsert_position_local(
            session,
            account_id=req.account_id,
            symbol=req.symbol,
            qty=pos_qty,
            provenance={"source": "paper_adapter"},
        )
        balances = self.adapter.get_balances()
        session.add(
            BalanceSnapshot(
                account_id=req.account_id,
                equity=d(balances["cash"]),
                margin=None,
                ts=now,
                source="paper",
            )
        )
        cursor = session.get(ExecutionCursor, req.account_id)
        if cursor is None:
            session.add(
                ExecutionCursor(
                    account_id=req.account_id,
                    cursor=str(len(self.adapter.list_executions()["items"])),
                    overlap_policy="overlap",
                )
            )
        else:
            cursor.cursor = str(len(self.adapter.list_executions()["items"]))

        reservation = session.get(RiskReservation, reservation_id)
        if reservation is not None:
            reservation.state = "CONSUMED"
        self.risk.release(reservation_id)

        if req.stop_price is not None:
            sync_protection(
                self.adapter,
                self.gate,
                client_order_id=client_order_id,
                symbol=req.symbol,
                filled_qty=d(order["filled_qty"]),
                stop_price=req.stop_price,
            )
