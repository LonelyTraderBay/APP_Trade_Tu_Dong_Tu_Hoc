"""Unit tests for Decimal/clock/redaction primitives."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from autotrade.core.domain.clock import ClockPort, FrozenClock
from autotrade.core.domain.ids import IdFactory
from autotrade.core.domain.money import d, quantize
from autotrade.core.domain.redaction import redact_mapping, redact_text


def test_money_rejects_float() -> None:
    with pytest.raises(TypeError):
        d(1.23)  # type: ignore[arg-type]


def test_money_quantize() -> None:
    assert quantize(d("1.234567891"), "0.00000001") == Decimal("1.23456789")


def test_clock_utc_aware() -> None:
    clock = ClockPort()
    assert clock.now_utc().value.tzinfo is not None


def test_frozen_clock_and_ids() -> None:
    wall = datetime(2026, 7, 23, 4, 0, tzinfo=UTC)
    clock = FrozenClock(wall, mono=10.0)
    assert clock.now_utc().value == wall
    clock.advance_mono(1.5)
    assert clock.monotonic() == 11.5
    factory = IdFactory(prefix="t_")
    assert factory.uuid4().startswith("t_")
    assert factory.client_order_id().startswith("t_c_")


def test_redaction() -> None:
    payload = {"api_key": "secret-value", "mode": "PAPER", "nested": {"token": "abc"}}
    redacted = redact_mapping(payload)
    assert redacted["api_key"] == "***REDACTED***"
    assert redacted["nested"]["token"] == "***REDACTED***"
    assert "Bearer ***REDACTED***" in redact_text("Bearer abcdef.ghij")
