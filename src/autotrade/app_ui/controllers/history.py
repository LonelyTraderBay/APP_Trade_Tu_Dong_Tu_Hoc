"""T051 — History controller: filtered read + CSV export, Qt-free.

Contract (`contracts/ui-core-boundary.md`): `export_history_csv` is **No
PIN**, redacted fields only. This controller never touches raw payloads —
`export_csv` writes exactly the `HistoryRow` objects `query` already
returned, never re-fetching from the database.
"""

from __future__ import annotations

from pathlib import Path

from autotrade.app_ui.services.history import (
    HistoryFilter,
    HistoryRow,
    export_history_csv,
    query_history,
)
from autotrade.persistence.uow import UnitOfWork


class HistoryController:
    """Bridges the History screen to the redacted audit-log projection."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def query(self, filt: HistoryFilter) -> list[HistoryRow]:
        """Read-only, filtered projection for the History table."""
        with self._uow.session() as session:
            return query_history(session, filt)

    def export_csv(self, rows: list[HistoryRow], path: Path) -> None:
        """No PIN. Writes only the already-redacted fields in `rows`."""
        export_history_csv(rows, path)
