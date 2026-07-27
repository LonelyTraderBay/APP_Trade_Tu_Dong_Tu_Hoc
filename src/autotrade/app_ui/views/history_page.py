"""T051 — History page: filter + redacted CSV export.

Filter inputs are plain `QLineEdit`s — this codebase has no prior
`QDateEdit`/date-picker usage (`live_monitor_page.py` is the first
`QTableWidget`, and no screen before this one takes a date range at all), so
per the task brief a simple ISO-8601 text field is used for since/until
rather than introducing a new widget type for one screen. Invalid dates are
rejected with a warning dialog, never silently ignored.

The results table reuses the exact `QTableWidget` read-only pattern from
`live_monitor_page.py` (`NoEditTriggers`, `SelectRows`, stretch header).
"Export CSV" opens `QFileDialog.getSaveFileName` and hands the *already
rendered* `HistoryRow` list to `HistoryController.export_csv` — it never
re-queries the database, so the exported file always matches what is on
screen.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from autotrade.app_ui.controllers.history import HistoryController
from autotrade.app_ui.services.history import HistoryFilter, HistoryRow, parse_iso_datetime

_COLUMNS = ("At", "Type", "Correlation ID", "Client Order ID", "Payload (redacted)")


class HistoryPage(QWidget):
    """History screen: type/correlation/client-order/time filters + CSV export."""

    def __init__(
        self, controller: HistoryController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("historyPage")
        self._controller = controller
        self._rows: list[HistoryRow] = []

        title = QLabel("History")
        title.setObjectName("pageTitle")
        font = title.font()
        font.setPointSize(font.pointSize() + 6)
        font.setBold(True)
        title.setFont(font)

        # --- filter form -----------------------------------------------
        self.type_input = QLineEdit()
        self.type_input.setObjectName("typeInput")
        self.type_input.setPlaceholderText("e.g. ui.tray.pause_l1")

        self.correlation_input = QLineEdit()
        self.correlation_input.setObjectName("correlationInput")

        self.client_order_input = QLineEdit()
        self.client_order_input.setObjectName("clientOrderInput")

        self.since_input = QLineEdit()
        self.since_input.setObjectName("sinceInput")
        self.since_input.setPlaceholderText("YYYY-MM-DDTHH:MM:SS (UTC)")

        self.until_input = QLineEdit()
        self.until_input.setObjectName("untilInput")
        self.until_input.setPlaceholderText("YYYY-MM-DDTHH:MM:SS (UTC)")

        self.apply_filter_button = QPushButton("Apply filter")
        self.apply_filter_button.setObjectName("applyFilterButton")
        self.apply_filter_button.clicked.connect(self.refresh)

        filter_grid = QGridLayout()
        filter_grid.addWidget(QLabel("Type:"), 0, 0)
        filter_grid.addWidget(self.type_input, 0, 1)
        filter_grid.addWidget(QLabel("Correlation ID:"), 0, 2)
        filter_grid.addWidget(self.correlation_input, 0, 3)
        filter_grid.addWidget(QLabel("Client Order ID:"), 1, 0)
        filter_grid.addWidget(self.client_order_input, 1, 1)
        filter_grid.addWidget(QLabel("Since:"), 1, 2)
        filter_grid.addWidget(self.since_input, 1, 3)
        filter_grid.addWidget(QLabel("Until:"), 2, 0)
        filter_grid.addWidget(self.until_input, 2, 1)
        filter_grid.addWidget(self.apply_filter_button, 2, 3)

        # --- table -----------------------------------------------------
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setObjectName("historyTable")
        self.table.setHorizontalHeaderLabels(list(_COLUMNS))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # --- export toolbar ----------------------------------------------
        export_bar = QWidget()
        export_layout = QHBoxLayout(export_bar)
        export_layout.setContentsMargins(0, 0, 0, 0)
        self.export_button = QPushButton("Export CSV")
        self.export_button.setObjectName("exportCsvButton")
        self.export_button.clicked.connect(self._on_export_csv)
        self.export_result_label = QLabel("")
        self.export_result_label.setObjectName("exportResultLabel")
        self.export_result_label.setWordWrap(True)
        export_layout.addWidget(self.export_button)
        export_layout.addWidget(self.export_result_label, 1)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(separator)
        layout.addLayout(filter_grid)
        layout.addWidget(self.table, 1)
        layout.addWidget(export_bar)

        self.refresh()

    # --- state -----------------------------------------------------------

    def _current_filter(self) -> HistoryFilter | None:
        """Build the filter from the form; returns None (after a warning) on
        a malformed since/until value rather than silently dropping it."""
        since = None
        until = None
        try:
            if self.since_input.text().strip():
                since = parse_iso_datetime(self.since_input.text())
            if self.until_input.text().strip():
                until = parse_iso_datetime(self.until_input.text())
        except ValueError as exc:
            QMessageBox.warning(
                self, "Invalid date", f"Could not parse since/until date:\n{exc}"
            )
            return None

        return HistoryFilter(
            type=self.type_input.text().strip() or None,
            correlation_id=self.correlation_input.text().strip() or None,
            client_order_id=self.client_order_input.text().strip() or None,
            since=since,
            until=until,
        )

    def refresh(self) -> None:
        """Re-read the controller with the current filter and repaint the table."""
        filt = self._current_filter()
        if filt is None:
            return
        try:
            rows = self._controller.query(filt)
        except Exception as exc:  # noqa: BLE001 - a query must never crash the page
            self.export_result_label.setText(f"Session unavailable — {type(exc).__name__}")
            self.table.setRowCount(0)
            self._rows = []
            return
        self._render(rows)

    def _render(self, rows: list[HistoryRow]) -> None:
        self._rows = rows
        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            self._set_row(row_idx, row)

    def _set_row(self, row_idx: int, row: HistoryRow) -> None:
        values = (
            row.at.isoformat(timespec="seconds"),
            row.type,
            row.correlation_id or "—",
            row.client_order_id or "—",
            str(row.payload_redacted or {}),
        )
        for col_idx, value in enumerate(values):
            self.table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    # --- actions -----------------------------------------------------------

    def _on_export_csv(self) -> None:
        if not self._rows:
            QMessageBox.information(self, "Nothing to export", "No rows to export yet.")
            return
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Export history CSV", "history.csv", "CSV files (*.csv)"
        )
        if not path_str:
            return
        try:
            self._controller.export_csv(self._rows, Path(path_str))
        except Exception as exc:  # noqa: BLE001 - export must never crash the page
            self.export_result_label.setText(f"Export failed — {type(exc).__name__}")
            QMessageBox.warning(self, "Export failed", f"Could not write CSV:\n{exc}")
            return
        self.export_result_label.setText(f"Exported {len(self._rows)} rows to {path_str}")
