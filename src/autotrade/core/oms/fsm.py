"""Order intent FSM + delivery-certainty axis."""

from __future__ import annotations

from enum import StrEnum


class IntentState(StrEnum):
    CREATED = "CREATED"
    RISK_REJECTED = "RISK_REJECTED"
    RESERVED = "RESERVED"
    SUBMITTING = "SUBMITTING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCEL_UNKNOWN = "CANCEL_UNKNOWN"
    #: A cancel that the broker confirmed took effect (order is terminal and
    #: inert, no exposure). Deliberately distinct from `REJECTED`, which
    #: means "the broker refused the order attempt" elsewhere in this
    #: codebase (see `submit.py`) — conflating an intentional, successful
    #: cancel with a broker rejection would misclassify it in any future
    #: reporting that counts `REJECTED` as a failure. See `cancel.py` module
    #: docstring for the full justification.
    CANCELED = "CANCELED"


class DeliveryCertainty(StrEnum):
    NOT_SENT = "NOT_SENT"
    SENDING = "SENDING"
    CONFIRMED = "CONFIRMED"
    MAY_HAVE_BEEN_ACCEPTED = "MAY_HAVE_BEEN_ACCEPTED"


_ALLOWED: dict[IntentState, frozenset[IntentState]] = {
    IntentState.CREATED: frozenset(
        {IntentState.RISK_REJECTED, IntentState.RESERVED}
    ),
    IntentState.RESERVED: frozenset({IntentState.SUBMITTING}),
    IntentState.SUBMITTING: frozenset(
        {
            IntentState.ACKNOWLEDGED,
            IntentState.FILLED,
            IntentState.REJECTED,
            IntentState.UNKNOWN,
        }
    ),
    IntentState.ACKNOWLEDGED: frozenset(
        {IntentState.FILLED, IntentState.CANCEL_REQUESTED, IntentState.REJECTED}
    ),
    IntentState.CANCEL_REQUESTED: frozenset(
        {
            IntentState.FILLED,
            IntentState.CANCELED,
            IntentState.CANCEL_UNKNOWN,
            IntentState.REJECTED,
        }
    ),
    IntentState.UNKNOWN: frozenset(
        {IntentState.FILLED, IntentState.REJECTED, IntentState.ACKNOWLEDGED}
    ),
    IntentState.CANCEL_UNKNOWN: frozenset(
        {IntentState.FILLED, IntentState.CANCELED, IntentState.REJECTED}
    ),
    IntentState.RISK_REJECTED: frozenset(),
    IntentState.FILLED: frozenset(),
    IntentState.REJECTED: frozenset(),
    IntentState.CANCELED: frozenset(),
}


def can_transition(current: IntentState, new: IntentState) -> bool:
    return new in _ALLOWED.get(current, frozenset())


def transition(current: IntentState, new: IntentState) -> IntentState:
    if not can_transition(current, new):
        raise ValueError(f"illegal FSM transition {current} → {new}")
    return new
