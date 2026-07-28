"""Durable OMS cancel: commit CANCEL_REQUESTED before the adapter call.

Mirrors `DurableSubmitter.submit()`'s crash-safety discipline
(`oms/submit.py`): (a) commit the `CANCEL_REQUESTED` transition to the DB
*before* calling the adapter, so a crash between the commit and the adapter
call is recoverable — a restart / recon can see `CANCEL_REQUESTED` and know
a cancel was in flight; (b) call the adapter exactly once; (c) if the
adapter raises AFTER it was actually invoked, mark `CANCEL_UNKNOWN` and
persist it — NEVER retry `cancel_order` for the same intent from within
this module. A `CANCEL_UNKNOWN` intent must be resolved later by querying
the broker (or by recon), the same discipline `oms/unknown.py::
resolve_unknown` already applies to a plain `UNKNOWN` submit intent.

REJECTED vs. CANCELED (decision, see also `fsm.py`): a cancel that the
broker confirms took effect lands in the new terminal `IntentState.CANCELED`
rather than being folded into `IntentState.REJECTED`. `REJECTED` means "the
broker refused/rejected the order attempt" everywhere else this state
machine uses it (`submit.py`'s SUBMITTING -> REJECTED edge, and the
CANCEL_REQUESTED -> REJECTED edge for "cancel raced with the broker
rejecting the order for an unrelated reason"). An intentional, successful,
owner-requested cancel is a fundamentally different outcome from a broker
rejection, and nothing in this codebase currently distinguishes them if
they shared a label — which is exactly the kind of silent misclassification
that would bite a future report/audit that counts `REJECTED` as a failure
signal. `CANCELED` is a plain Python `StrEnum` value on a `String` column
(no DB migration), so the additive cost is one enum member + one FSM
transition entry — cheap insurance for a distinction that matters.

This module intentionally never touches `RiskEngine`. Canceling an order
does not increase exposure, and by the time an intent reaches
`ACKNOWLEDGED` (the only state cancel is legal from, per the FSM) its risk
reservation has already been released — `resolve_unknown` releases the
reservation the moment the order is confirmed to exist on the broker,
whether or not it has filled. There is nothing here for cancel to check,
reserve, or release, and no `reduce_only` concept applies — that flag is
specific to `flatten.py`'s exposure-reducing *order submission* path, not
this cancel-of-an-existing-order path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from autotrade.core.adapters.protocol import BrokerAdapter
from autotrade.core.domain.ids import IdFactory
from autotrade.core.domain.redaction import redact_mapping
from autotrade.core.oms.fsm import DeliveryCertainty, IntentState, transition
from autotrade.persistence.models import AuditEvent, Order, OrderIntent
from autotrade.persistence.uow import UnitOfWork


@dataclass(frozen=True, slots=True)
class CancelResult:
    """Outcome of a cancel attempt — typed, never a bare string.

    `ok=True` means the intent reached a confidently-known terminal state:
    `FILLED` (the cancel arrived too late, the order had already filled) or
    `CANCELED` (the cancel took effect). `ok=False` always carries `error`;
    when the outcome could not be confidently resolved — the adapter raised
    after being called, or it returned a response this module doesn't
    recognize as FILLED/CANCELED — `state` is `CANCEL_UNKNOWN` and the
    caller must resolve it later via a query/recon path, never by calling
    this function again for the same intent.
    """

    ok: bool
    state: str | None = None
    error: str | None = None


def cancel_intent(
    uow: UnitOfWork,
    adapter: BrokerAdapter,
    *,
    intent_id: str,
    ids: IdFactory | None = None,
) -> CancelResult:
    ids = ids or IdFactory()

    with uow.session() as session:
        intent = session.get(OrderIntent, intent_id)
        if intent is None:
            return CancelResult(ok=False, error=f"unknown intent: {intent_id}")

        if intent.state != IntentState.ACKNOWLEDGED.value:
            return CancelResult(
                ok=False, error=f"cannot cancel from state {intent.state}"
            )

        order_row = session.query(Order).filter(Order.intent_id == intent_id).one_or_none()
        if order_row is None or not order_row.broker_order_id:
            return CancelResult(ok=False, error="no broker_order_id on record for intent")

        broker_order_id = order_row.broker_order_id

        # --- Crash-safety point: commit CANCEL_REQUESTED before the
        # adapter call (mirrors `DurableSubmitter._persist_pre_submit`'s
        # "commit before send"). If the process dies right here, a restart
        # / recon sees CANCEL_REQUESTED and knows a cancel was in flight.
        intent.state = transition(IntentState.ACKNOWLEDGED, IntentState.CANCEL_REQUESTED).value
        order_row.state = intent.state
        session.add(
            AuditEvent(
                event_id=ids.uuid4(),
                type="intent_cancel_requested",
                payload_redacted={
                    "intent_id": intent_id,
                    "broker_order_id": broker_order_id,
                },
                at=datetime.now(UTC),
                correlation_id=intent_id,
            )
        )
        session.flush()

    # --- Post-commit: call the adapter exactly once. From here on, any
    # exception means we do not know whether the broker received/actioned
    # the cancel — CANCEL_UNKNOWN, never a blind retry.
    try:
        response = adapter.cancel_order(broker_order_id=broker_order_id)
    except Exception as exc:  # noqa: BLE001
        _persist_terminal(
            uow,
            ids,
            intent_id=intent_id,
            broker_order_id=broker_order_id,
            new_state=IntentState.CANCEL_UNKNOWN,
            delivery=DeliveryCertainty.MAY_HAVE_BEEN_ACCEPTED,
            audit_type="intent_cancel_unknown",
            audit_extra={"error": str(exc)},
        )
        return CancelResult(ok=False, state=IntentState.CANCEL_UNKNOWN.value, error=str(exc))

    final_state = _interpret_cancel_response(response)
    # A confidently-resolved outcome (FILLED/CANCELED) means the broker gave
    # a clean, unambiguous answer — CONFIRMED, same as `_finalize_fill`. An
    # unrecognized response leaves us as uncertain as an adapter exception
    # would have — MAY_HAVE_BEEN_ACCEPTED, same as the exception branch.
    delivery = (
        DeliveryCertainty.CONFIRMED
        if final_state is not IntentState.CANCEL_UNKNOWN
        else DeliveryCertainty.MAY_HAVE_BEEN_ACCEPTED
    )
    _persist_terminal(
        uow,
        ids,
        intent_id=intent_id,
        broker_order_id=broker_order_id,
        new_state=final_state,
        delivery=delivery,
        audit_type="intent_cancel_resolved",
        audit_extra={"response": response},
        # G1.4 — the terminal cancel_order() response is just as worth
        # preserving as _finalize_fill's fill-time order dict (same
        # adapter-agnostic dict shape: PaperAdapter's own order dict, or
        # CcxtDemoAdapter's normalized dict nesting the real ccxt payload
        # under "raw"). Only available here in the resolved branch — the
        # exception branch above never received a response to persist.
        raw_reference=response,
    )

    if final_state is IntentState.CANCEL_UNKNOWN:
        return CancelResult(
            ok=False,
            state=final_state.value,
            error=f"cancel response not confidently resolved: {response}",
        )
    return CancelResult(ok=True, state=final_state.value)


def _interpret_cancel_response(response: dict[str, Any]) -> IntentState:
    """Map an adapter's `cancel_order()` response to a terminal state.

    Both `PaperAdapter` and `CcxtDemoAdapter` report the *pre-cancel* order
    state under `"state"` when the cancel arrived too late: `PaperAdapter`
    returns `{**order, "cancel": "TOO_LATE"}` where `state` is still
    `"FILLED"` from the original order; `CcxtDemoAdapter._normalize_order`
    reports `"FILLED"` whenever the underlying ccxt status is `closed` with
    the full quantity filled. So checking `state == "FILLED"` catches "too
    late" uniformly across both adapters without inspecting adapter-specific
    keys like Paper's `"cancel"`.

    A `state == "CANCELED"` means the cancel genuinely took effect — Paper
    sets this exact spelling explicitly on success, and
    `_normalize_order` maps ccxt's `"canceled"`/`"cancelled"` status to the
    same spelling.

    Anything else — e.g. `"NOT_FOUND"` (broker/adapter has no record of this
    order), or a response that is still open (the cancel silently didn't
    take) — is not confidently one of the two known-good outcomes.
    Conservatively treated as unresolved (`CANCEL_UNKNOWN`) rather than
    guessed at, matching this codebase's "only trust a confirmed broker
    answer" discipline (see `oms/unknown.py::resolve_unknown`'s
    `found is None` branch, which holds rather than assumes).
    """
    state = str(response.get("state") or "")
    if state == "FILLED":
        return IntentState.FILLED
    if state == "CANCELED":
        return IntentState.CANCELED
    return IntentState.CANCEL_UNKNOWN


def _persist_terminal(
    uow: UnitOfWork,
    ids: IdFactory,
    *,
    intent_id: str,
    broker_order_id: str,
    new_state: IntentState,
    delivery: DeliveryCertainty,
    audit_type: str,
    audit_extra: dict[str, Any],
    raw_reference: dict[str, Any] | None = None,
) -> None:
    with uow.session() as session:
        intent = session.get(OrderIntent, intent_id)
        order_row = session.query(Order).filter(Order.intent_id == intent_id).one()
        if intent is not None:
            intent.state = transition(IntentState.CANCEL_REQUESTED, new_state).value
            order_row.state = intent.state
            order_row.delivery_certainty = delivery.value
        if raw_reference is not None:
            order_row.raw_reference = redact_mapping(raw_reference)
        session.add(
            AuditEvent(
                event_id=ids.uuid4(),
                type=audit_type,
                payload_redacted={
                    "intent_id": intent_id,
                    "broker_order_id": broker_order_id,
                    **audit_extra,
                },
                at=datetime.now(UTC),
                correlation_id=intent_id,
            )
        )
