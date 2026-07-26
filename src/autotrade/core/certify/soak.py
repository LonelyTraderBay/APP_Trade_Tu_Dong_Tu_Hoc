"""Soak run state machine — wall-clock 72h, Owner pause fails gate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from autotrade.core.certify import records as cert_records
from autotrade.core.domain.ids import IdFactory
from autotrade.persistence.models import SoakRun

SOAK_REQUIRED = timedelta(hours=72)


def _as_utc(dt: datetime) -> datetime:
    """SQLite/SQLAlchemy often returns naive UTC; comparisons need aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


@dataclass
class SoakController:
    session: Session
    account_id: str
    ids: IdFactory | None = None

    def __post_init__(self) -> None:
        if self.ids is None:
            self.ids = IdFactory()

    def start(self) -> SoakRun:
        run = SoakRun(
            soak_id=self.ids.new("soak"),
            account_id=self.account_id,
            started_at=datetime.now(UTC),
            owner_paused=False,
            passed=False,
            unresolved_recon_at_end=0,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def mark_owner_pause(self, soak_id: str) -> SoakRun:
        run = self.session.get(SoakRun, soak_id)
        if run is None:
            raise KeyError(soak_id)
        run.owner_paused = True
        run.passed = False
        run.ended_at = datetime.now(UTC)
        self.session.add(run)
        return run

    def complete(
        self,
        soak_id: str,
        *,
        unresolved_recon: int,
        now: datetime | None = None,
    ) -> SoakRun:
        run = self.session.get(SoakRun, soak_id)
        if run is None:
            raise KeyError(soak_id)
        end = _as_utc(now or datetime.now(UTC))
        run.ended_at = end
        run.unresolved_recon_at_end = unresolved_recon
        if run.owner_paused:
            run.passed = False
        else:
            started = _as_utc(run.started_at)
            duration = end - started
            run.passed = duration >= SOAK_REQUIRED and unresolved_recon == 0
            if run.passed:
                cert_records.mark_soak_passed(
                    self.session, started_at=started, ended_at=end
                )
        self.session.add(run)
        return run
