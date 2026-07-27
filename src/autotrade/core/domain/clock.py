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


#: Default gap (wall-vs-monotonic divergence) past which `detect_clock_jump`
#: treats the process as having lived through a suspicious clock event
#: (sleep/resume, NTP step, manual clock change). Matches ADR-D12's own
#: ">5 minutes" example — long enough that ordinary scheduling jitter,
#: GC pauses, or a slow test runner never trips it, short enough that a real
#: sleep/resume (typically minutes to hours) always does.
DEFAULT_CLOCK_SKEW_THRESHOLD_SECONDS = 300.0


@dataclass(frozen=True, slots=True)
class ClockJumpResult:
    """Outcome of `detect_clock_jump` — never raises, always this shape."""

    jumped: bool
    reason: str | None = None


def detect_clock_jump(
    clock: ClockPort,
    *,
    last_wall: Instant | None,
    last_mono: float | None = None,
    threshold_seconds: float = DEFAULT_CLOCK_SKEW_THRESHOLD_SECONDS,
) -> ClockJumpResult:
    """Detect a suspicious clock jump from a previous checkpoint (ADR-D12).

    Implements two independent checks, each valid under different
    preconditions — read both before calling this from a new site:

    1. **Backward wall-clock (cross-restart safe).** If `last_wall` is not
       `None` and `clock.now_utc()` reads *before* it, the wall clock moved
       backward (set back manually, an NTP correction, or otherwise
       unreliable) since `last_wall` was recorded. This holds whether
       `last_wall` came from this process or a previous one, because it only
       ever compares two absolute UTC instants — never a `monotonic()`
       value. This is therefore the ONLY signal in this function that is
       safe to persist across a process restart and re-check later:
       `time.monotonic()`'s reference point is arbitrary per-process and
       resets on every restart, so a monotonic value from a prior run is
       meaningless to a new one.

       A large *forward* wall-clock gap alone is NOT reported here — the app
       being closed for a long time (hours, days) is normal, not a fault.
       Forward jumps are only meaningful together with a same-process
       monotonic baseline (check 2).

    2. **Monotonic-vs-wall divergence (same-process only).** If BOTH
       `last_wall` and `last_mono` are given, compares how far the wall
       clock moved (`wall_delta`) against how far the monotonic clock moved
       over the same interval (`mono_delta`). `time.monotonic()` does not
       advance during OS sleep/hibernate (Windows and POSIX), while the wall
       clock keeps ticking or jumps forward at resume — so `wall_delta`
       exceeding `mono_delta` by more than `threshold_seconds` is the
       sleep/resume signature (also catches an NTP step or a manual clock
       change made while the process stayed alive).

       PRECONDITION the caller must guarantee: `last_mono` was read from the
       same `ClockPort` instance / the same OS process as the `clock`
       passed here. A monotonic reading from a different process is not
       comparable to this one — pass `last_mono=None` whenever there is no
       same-process baseline yet (e.g. at the very first check after a
       fresh launch).

    Neither check raises; an absent baseline (`last_wall=None`) simply
    means "nothing to compare against yet" — not a jump.
    """
    if last_wall is None:
        return ClockJumpResult(jumped=False, reason=None)

    now = clock.now_utc()
    wall_delta = (now.value - last_wall.value).total_seconds()

    if wall_delta < 0:
        return ClockJumpResult(
            jumped=True,
            reason=f"clock_skew_backward:{wall_delta:.1f}s",
        )

    if last_mono is not None:
        mono_delta = clock.monotonic() - last_mono
        divergence = wall_delta - mono_delta
        if divergence > threshold_seconds:
            return ClockJumpResult(
                jumped=True,
                reason=f"clock_skew_monotonic_divergence:{divergence:.1f}s",
            )

    return ClockJumpResult(jumped=False, reason=None)
