"""T041 — Live Monitor page: read-only intents table, no blind-retry button.

Contract (`contracts/ui-core-boundary.md` + tasks.md T041): this screen is
**read-only display**. There is deliberately no button that resubmits or
retries an order — the only interactive controls are "Refresh" (re-fetch the
page) and a page-size limit spinner. In-flight intents
(`LiveMonitorRow.needs_attention`, which includes UNKNOWN) are never hidden
or paginated away — see `build_live_monitor_page`'s hard guarantee — and are
marked with a leading "⚠" in a status column. `QTableWidget` has no prior
usage/color convention in this codebase, so a text marker is used rather
than inventing a background colour that might not render meaningfully in
every Qt theme. `page.truncated` is always surfaced as a label, never
silently dropped.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from autotrade.app_ui.controllers.live_monitor import LiveMonitorController
from autotrade.app_ui.services.dashboard import DEFAULT_LIVE_MONITOR_LIMIT, LiveMonitorRow
from autotrade.app_ui.services.dashboard import LiveMonitorPage as LiveMonitorPageModel

ATTENTION_MARKER = "⚠"

_COLUMNS = (
    "Status",
    "Intent ID",
    "Client Order ID",
    "State",
    "Delivery Certainty",
    "Symbol",
    "Side",
    "Qty",
    "Created At",
)


class LiveMonitorPage(QWidget):
    """Live Monitor screen: read-only orders/intents table incl. UNKNOWN.

    Read-only by design: no widget here can resubmit, cancel, or otherwise
    mutate an order/intent. Only "Refresh" (re-fetch) and the page-size
    spinner are interactive.
    """

    def __init__(
        self, controller: LiveMonitorController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("liveMonitorPage")
        self._controller = controller

        title = QLabel("Live Monitor")
        title.setObjectName("pageTitle")
        font = title.font()
        font.setPointSize(font.pointSize() + 6)
        font.setBold(True)
        title.setFont(font)

        # --- toolbar (Refresh + page size only — no mutating controls) -----
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self.limit_spin = QSpinBox()
        self.limit_spin.setObjectName("limitSpin")
        self.limit_spin.setRange(1, 5000)
        self.limit_spin.setValue(DEFAULT_LIVE_MONITOR_LIMIT)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.clicked.connect(self.refresh)

        toolbar_layout.addWidget(QLabel("Page size:"))
        toolbar_layout.addWidget(self.limit_spin)
        toolbar_layout.addWidget(self.refresh_button)
        toolbar_layout.addStretch(1)

        # --- table -----------------------------------------------------
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setObjectName("intentsTable")
        self.table.setHorizontalHeaderLabels(list(_COLUMNS))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.truncated_label = QLabel("")
        self.truncated_label.setObjectName("truncatedLabel")
        self.truncated_label.setWordWrap(True)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(separator)
        layout.addWidget(toolbar)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.truncated_label)

        self.refresh()

    # --- state -----------------------------------------------------------

    def refresh(self) -> None:
        """Re-fetch the page from the controller and repaint the table."""
        try:
            page = self._controller.page(limit=self.limit_spin.value())
        except Exception as exc:  # noqa: BLE001 - a fetch must never crash the page
            self.truncated_label.setText(f"Session unavailable — {type(exc).__name__}")
            self.table.setRowCount(0)
            return
        self._render(page)

    def _render(self, page: LiveMonitorPageModel) -> None:
        self.table.setRowCount(len(page.rows))
        for row_idx, row in enumerate(page.rows):
            self._set_row(row_idx, row)

        if page.truncated:
            self.truncated_label.setText(
                f"{page.truncated} more settled rows not shown "
                f"(showing {len(page.rows)} of {page.total})."
            )
        else:
            self.truncated_label.setText(f"Showing all {page.total} intents.")

    def _set_row(self, row_idx: int, row: LiveMonitorRow) -> None:
        values = (
            ATTENTION_MARKER if row.needs_attention else "",
            row.intent_id,
            row.client_order_id,
            row.state,
            row.delivery_certainty or "—",
            row.symbol,
            row.side,
            str(row.qty),
            row.created_at.isoformat(timespec="seconds"),
        )
        for col_idx, value in enumerate(values):
            self.table.setItem(row_idx, col_idx, QTableWidgetItem(value))
