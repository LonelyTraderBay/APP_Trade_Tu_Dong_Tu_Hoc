"""Clock ports: UTC wall clock + monotonic durations (ADR-D12)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic


@dataclass(frozen=True, slots=True)
class Instant:
    """UTC wall-clock instant."""

    value: datetime

    def __post_init__(self) -> None:
        if self.value.tzinfo is None:
            raise ValueError("Instant requires timezone-aware UTC datetime")


class ClockPort:
    """Injectable clock for deterministic tests."""

    def now_utc(self) -> Instant:
        return Instant(datetime.now(UTC))

    def monotonic(self) -> float:
        return monotonic()


class FrozenClock(ClockPort):
    """Test double: fixed wall time + controllable monotonic."""

    def __init__(self, wall: datetime, mono: float = 0.0) -> None:
        if wall.tzinfo is None:
            raise ValueError("FrozenClock wall must be timezone-aware")
        self._wall = wall.astimezone(UTC)
        self._mono = mono

    def now_utc(self) -> Instant:
        return Instant(self._wall)

    def monotonic(self) -> float:
        return self._mono

    def advance_mono(self, seconds: float) -> None:
        self._mono += seconds
