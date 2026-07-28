"""OMS FSM transition tests."""

from __future__ import annotations

import pytest

from autotrade.core.oms.fsm import IntentState, can_transition, transition


@pytest.mark.d1a
def test_legal_and_illegal_transitions() -> None:
    assert can_transition(IntentState.CREATED, IntentState.RESERVED)
    assert transition(IntentState.RESERVED, IntentState.SUBMITTING) == IntentState.SUBMITTING
    with pytest.raises(ValueError):
        transition(IntentState.FILLED, IntentState.CREATED)
    assert can_transition(IntentState.SUBMITTING, IntentState.UNKNOWN)
    assert can_transition(IntentState.UNKNOWN, IntentState.FILLED)
