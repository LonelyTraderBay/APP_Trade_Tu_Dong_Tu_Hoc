"""PIN Argon2id hash + lockout counters."""

from __future__ import annotations

from datetime import UTC, datetime

from autotrade.persistence.pin import hash_pin, verify_pin


def test_pin_hash_and_verify_ok() -> None:
    state = hash_pin("2468")
    result = verify_pin(state, "2468")
    assert result.ok is True
    assert result.state.failed_count == 0


def test_pin_failure_increments_and_lockout() -> None:
    state = hash_pin("2468")
    now = datetime(2026, 7, 23, 4, 0, tzinfo=UTC)
    current = state
    for _ in range(5):
        result = verify_pin(current, "0000", now=now)
        assert result.ok is False
        current = result.state
    assert current.failed_count == 5
    assert current.lockout_until is not None
    locked = verify_pin(current, "2468", now=now)
    assert locked.ok is False
