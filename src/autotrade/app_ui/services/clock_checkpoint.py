"""Wall-clock checkpoint persistence (ADR-D12), Qt-free.

`app_ui/services/startup.py::run_desktop_startup_recovery` needs a
cross-restart signal for "did the wall clock move backward since we last saw
it". `time.monotonic()` cannot answer that — its reference point is
arbitrary per-process and resets on every restart (see
`core/domain/clock.py::detect_clock_jump`'s docstring) — so the only value
worth persisting across launches is a wall-clock `Instant`.

Reuses the existing generic `app_settings` key/value table (`AppSetting`),
same pattern as `app_ui/services/settings.py::read_autostart_setting`/
`write_autostart_setting` (one row, no new table/migration). Kept in its own
module rather than folded into `settings.py` because this checkpoint is
internal Startup Recovery state, not an Owner-facing Settings-screen
preference.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from autotrade.core.domain.clock import Instant
from autotrade.persistence.models import AppSetting

CLOCK_CHECKPOINT_SETTING_KEY = "clock.last_wall_checkpoint"


def read_last_wall_checkpoint(session: Session) -> Instant | None:
    """Last wall-clock checkpoint written by a successful recovery, if any.

    Returns `None` both when nothing has ever been written (fresh install)
    and when the stored value is unparseable (defensive — never raises on a
    corrupt/foreign value; treated the same as "no checkpoint yet").
    """
    row = session.get(AppSetting, CLOCK_CHECKPOINT_SETTING_KEY)
    if row is None:
        return None
    try:
        value = datetime.fromisoformat(row.value)
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return Instant(value)


def write_wall_checkpoint(session: Session, instant: Instant) -> None:
    """Persist `instant` as the latest known-good wall-clock checkpoint."""
    value = instant.value.astimezone(UTC).isoformat()
    row = session.get(AppSetting, CLOCK_CHECKPOINT_SETTING_KEY)
    if row is None:
        session.add(AppSetting(key=CLOCK_CHECKPOINT_SETTING_KEY, value=value))
    else:
        row.value = value
