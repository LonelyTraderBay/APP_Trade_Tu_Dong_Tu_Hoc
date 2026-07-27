"""Clock jump → recovery subset before trade (ADR-D12).

The previous version of this test was tautological: it built a
`FrozenClock`, called `.advance_mono(3600)`, then called
`run_startup_recovery(...)` — which takes no clock parameter at all, so the
advance had zero effect on the function under test. Deleting the clock lines
would not have changed the test's outcome.

Real detection now lives in `core.domain.clock.detect_clock_jump` (pure,
Qt-free — see its docstring for exactly what is/isn't detectable given that
`time.monotonic()`'s reference point resets on every process restart) plus
the cross-restart wiring in
`app_ui.services.startup.run_desktop_startup_recovery`, which persists a
wall-clock checkpoint (`app_ui.services.clock_checkpoint`, `AppSetting`-
backed) and re-checks it at the next launch.

This file covers, in order:
  1. `detect_clock_jump` in isolation (both checks, `FrozenClock`-driven).
  2. The checkpoint read/write helpers round-tripping through a real DB.
  3. `run_desktop_startup_recovery` end-to-end for the one path that is
     actually testable cross-process: a persisted checkpoint from the
     future relative to the real wall clock proves a backward jump.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from autotrade.app_ui.services.clock_checkpoint import (
    read_last_wall_checkpoint,
    write_wall_checkpoint,
)
from autotrade.app_ui.services.startup import run_desktop_startup_recovery
from autotrade.core.domain.clock import (
    ClockJumpResult,
    FrozenClock,
    Instant,
    detect_clock_jump,
)
from autotrade.core.oms.account_state import AccountStatus
from autotrade.persistence.models import Account, ReconBreak
from autotrade.persistence.uow import UnitOfWork

PAPER_ACCOUNT_ID = "paper1"


def _seed_paper_active(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add(
            Account(
                account_id=PAPER_ACCOUNT_ID,
                adapter_id="paper",
                mode="PAPER",
                status="READY",
                eligibility="PAPER",
                is_active=True,
            )
        )


# --- 1. detect_clock_jump in isolation -------------------------------------


@pytest.mark.d1a
def test_detect_clock_jump_no_checkpoint_is_never_a_jump() -> None:
    clock = FrozenClock(datetime(2026, 7, 23, 4, 0, tzinfo=UTC))

    result = detect_clock_jump(clock, last_wall=None, last_mono=None)

    assert result == ClockJumpResult(jumped=False, reason=None)


@pytest.mark.d1a
def test_detect_clock_jump_backward_wall_clock_is_detected() -> None:
    # The checkpoint is AHEAD of "now" -- the wall clock must have moved
    # backward (set back manually, or otherwise unreliable) since it was
    # recorded. This is the cross-restart-safe signal: it only ever compares
    # two absolute UTC instants, never a monotonic value from another
    # process.
    checkpoint = Instant(datetime(2026, 7, 23, 5, 0, tzinfo=UTC))
    clock = FrozenClock(datetime(2026, 7, 23, 4, 0, tzinfo=UTC))

    result = detect_clock_jump(clock, last_wall=checkpoint, last_mono=None)

    assert result.jumped is True
    assert result.reason is not None
    assert "backward" in result.reason


@pytest.mark.d1a
def test_detect_clock_jump_large_forward_gap_alone_is_not_suspicious() -> None:
    # The app being closed for days is normal, not a fault: a forward
    # wall-clock gap with no same-process monotonic baseline must NOT be
    # flagged, no matter how large.
    checkpoint = Instant(datetime(2026, 7, 20, 4, 0, tzinfo=UTC))
    clock = FrozenClock(datetime(2026, 7, 23, 4, 0, tzinfo=UTC))

    result = detect_clock_jump(clock, last_wall=checkpoint, last_mono=None)

    assert result.jumped is False


@pytest.mark.d1a
def test_detect_clock_jump_monotonic_divergence_detects_sleep_resume() -> None:
    # Same-process signal: wall clock moved far ahead while monotonic barely
    # moved -- the sleep/resume signature (also covers an NTP step or a
    # manual clock change made while the process stayed alive). `last_mono`
    # must have come from the same ClockPort/process as `clock`.
    last_wall = Instant(datetime(2026, 7, 23, 4, 0, tzinfo=UTC))
    last_mono = 1000.0
    clock = FrozenClock(datetime(2026, 7, 23, 4, 20, tzinfo=UTC), mono=1005.0)
    # wall moved 1200s, monotonic moved only 5s: monotonic barely advanced
    # while the wall clock jumped 20 minutes -- a classic sleep/resume.

    result = detect_clock_jump(
        clock, last_wall=last_wall, last_mono=last_mono, threshold_seconds=300.0
    )

    assert result.jumped is True
    assert result.reason is not None
    assert "monotonic" in result.reason


@pytest.mark.d1a
def test_detect_clock_jump_monotonic_divergence_under_threshold_is_fine() -> None:
    last_wall = Instant(datetime(2026, 7, 23, 4, 0, tzinfo=UTC))
    last_mono = 1000.0
    clock = FrozenClock(datetime(2026, 7, 23, 4, 1, tzinfo=UTC), mono=1058.0)
    # wall moved 60s, monotonic moved 58s: a 2s divergence, far under the
    # 300s threshold -- ordinary scheduling jitter, not a jump.

    result = detect_clock_jump(
        clock, last_wall=last_wall, last_mono=last_mono, threshold_seconds=300.0
    )

    assert result.jumped is False


# --- 2. checkpoint persistence helpers --------------------------------------


@pytest.mark.d1c
def test_checkpoint_helpers_roundtrip(migrated_uow: UnitOfWork) -> None:
    instant = Instant(datetime(2026, 7, 23, 4, 0, tzinfo=UTC))

    with migrated_uow.session() as session:
        assert read_last_wall_checkpoint(session) is None
        write_wall_checkpoint(session, instant)

    with migrated_uow.session() as session:
        loaded = read_last_wall_checkpoint(session)

    assert loaded is not None
    assert loaded.value == instant.value


# --- 3. end-to-end cross-restart path via run_desktop_startup_recovery -----


@pytest.mark.d1c
def test_startup_recovery_locks_when_checkpoint_is_ahead_of_now(
    migrated_uow: UnitOfWork,
) -> None:
    """A persisted checkpoint set in the future relative to the real wall
    clock proves the clock went backward (or was set back) since the launch
    that wrote it -- the one fault detectable from wall-clock-only,
    cross-process data, and the reason `run_desktop_startup_recovery` keeps
    the account SAFE_LOCK until recon runs rather than trading through it.
    """
    _seed_paper_active(migrated_uow)
    future_checkpoint = Instant(datetime.now(UTC) + timedelta(hours=2))
    with migrated_uow.session() as session:
        write_wall_checkpoint(session, future_checkpoint)

    result = run_desktop_startup_recovery(migrated_uow)

    assert result is not None
    assert result.ready is False
    assert result.status == AccountStatus.SAFE_LOCK
    assert any("clock_skew" in reason for reason in result.reasons)


@pytest.mark.d1c
def test_startup_recovery_writes_checkpoint_after_success(
    migrated_uow: UnitOfWork,
) -> None:
    _seed_paper_active(migrated_uow)
    with migrated_uow.session() as session:
        assert read_last_wall_checkpoint(session) is None

    result = run_desktop_startup_recovery(migrated_uow)

    assert result is not None
    assert result.ready is True
    with migrated_uow.session() as session:
        checkpoint = read_last_wall_checkpoint(session)
    assert checkpoint is not None


@pytest.mark.d1c
def test_startup_recovery_does_not_overwrite_checkpoint_on_locked_launch(
    migrated_uow: UnitOfWork,
) -> None:
    _seed_paper_active(migrated_uow)
    good_checkpoint = Instant(datetime.now(UTC) - timedelta(days=1))
    with migrated_uow.session() as session:
        write_wall_checkpoint(session, good_checkpoint)
        session.add(
            ReconBreak(
                type="orphan",
                payload={"account_id": PAPER_ACCOUNT_ID},
                status="OPEN",
                at=datetime.now(UTC),
            )
        )

    result = run_desktop_startup_recovery(migrated_uow)

    assert result is not None
    assert result.ready is False
    assert result.status == AccountStatus.SAFE_LOCK
    with migrated_uow.session() as session:
        checkpoint = read_last_wall_checkpoint(session)
    assert checkpoint is not None
    assert checkpoint.value == good_checkpoint.value
