"""T050 — Strategy controller: read-only snapshot, Qt-free.

Mirrors `LiveMonitorController`'s shape: this screen has no core command of
its own, only the `build_strategy_view` projection. There is deliberately no
mutating method here — the Strategy page shows the locked hard ceilings,
never editable params.
"""

from __future__ import annotations

from autotrade.app_ui.services.strategy import StrategyView, build_strategy_view
from autotrade.persistence.uow import UnitOfWork


class StrategyController:
    """Bridges the Strategy screen to the read-only strategy-binding projection."""

    def __init__(self, uow: UnitOfWork, *, account_id: str | None = None) -> None:
        self._uow = uow
        self._account_id = account_id

    def snapshot(self) -> StrategyView:
        """Read-only projection for the Strategy page."""
        with self._uow.session() as session:
            return build_strategy_view(session, account_id=self._account_id)
