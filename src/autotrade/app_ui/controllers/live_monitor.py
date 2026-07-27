"""T041 — Live Monitor controller: read-only intents page, Qt-free.

Contract (`contracts/ui-core-boundary.md`): the Live Monitor screen is
read-only — it has no core command of its own, only the
`build_live_monitor_page` projection. There is deliberately no retry/resubmit
method here (tasks.md: "no blind-retry button") — this controller cannot
mutate OMS state even if a future view asked it to.
"""

from __future__ import annotations

from autotrade.app_ui.services.dashboard import (
    DEFAULT_LIVE_MONITOR_LIMIT,
    LiveMonitorPage,
    build_live_monitor_page,
)
from autotrade.persistence.uow import UnitOfWork


class LiveMonitorController:
    """Bridges the Live Monitor screen to the read-only intents projection."""

    def __init__(self, uow: UnitOfWork, *, account_id: str | None = None) -> None:
        self._uow = uow
        self._account_id = account_id

    def page(self, *, limit: int = DEFAULT_LIVE_MONITOR_LIMIT) -> LiveMonitorPage:
        """Read-only projection for the Live Monitor page.

        Hard guarantee inherited from `build_live_monitor_page`: every
        in-flight intent (incl. UNKNOWN) is returned regardless of `limit`.
        """
        with self._uow.session() as session:
            return build_live_monitor_page(
                session, account_id=self._account_id, limit=limit
            )
