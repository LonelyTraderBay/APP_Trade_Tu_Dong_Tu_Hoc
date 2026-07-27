"""T051 — History page: filter + redacted CSV export through the real UI.

Skipped entirely when the optional `[ui]` extra (PySide6) is not installed --
same `qapp` fixture pattern as `test_broker_hub_ui.py`. `QFileDialog.getSaveFileName`
is monkeypatched to return a `tmp_path` file directly (same "capture instead
of blocking on a real modal" approach the broker-hub suite uses for
`QMessageBox.warning`), so the export test drives the exact button handler
path and inspects the resulting file on disk.
"""

from __future__ import annotations

import csv
import os
from datetime import UTC, datetime

import pytest

from autotrade.persistence.models import AuditEvent
from autotrade.persistence.uow import UnitOfWork

NOW = datetime(2026, 7, 27, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201 - QApplication, only when PySide6 exists
    pytest.importorskip("PySide6", reason="optional extra [ui] not installed")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _seed(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add_all(
            [
                AuditEvent(
                    event_id="e1",
                    type="ui.tray.pause_l1",
                    payload_redacted={"scope": "global", "reason": "tray_pause"},
                    at=NOW,
                    correlation_id=None,
                ),
                AuditEvent(
                    event_id="e2",
                    type="ui.broker_hub.test_connection",
                    payload_redacted={"api_key": "***REDACTED***", "ok": True},
                    at=NOW,
                    correlation_id=None,
                ),
            ]
        )


@pytest.mark.d1c
def test_history_page_loads_all_rows_with_no_filter(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.history import HistoryController
    from autotrade.app_ui.views.history_page import HistoryPage

    _seed(migrated_uow)
    page = HistoryPage(HistoryController(migrated_uow))
    try:
        assert page.table.rowCount() == 2
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_history_page_apply_filter_narrows_the_table(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.history import HistoryController
    from autotrade.app_ui.views.history_page import HistoryPage

    _seed(migrated_uow)
    page = HistoryPage(HistoryController(migrated_uow))
    try:
        page.type_input.setText("ui.tray.pause_l1")
        page.apply_filter_button.click()

        assert page.table.rowCount() == 1
        assert page.table.item(0, 1).text() == "ui.tray.pause_l1"
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_history_page_invalid_date_shows_a_warning_and_keeps_old_rows(
    qapp, migrated_uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
) -> None:
    from PySide6.QtWidgets import QMessageBox

    from autotrade.app_ui.controllers.history import HistoryController
    from autotrade.app_ui.views.history_page import HistoryPage

    _seed(migrated_uow)
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda parent, title, text: warnings.append((title, text))),
    )

    page = HistoryPage(HistoryController(migrated_uow))
    try:
        assert page.table.rowCount() == 2  # loaded fine at construction

        page.since_input.setText("not-a-date")
        page.apply_filter_button.click()

        assert len(warnings) == 1
        assert "date" in warnings[0][0].lower()
        # Old rows must not have been wiped by the rejected filter attempt.
        assert page.table.rowCount() == 2
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_export_csv_writes_a_real_file_with_redacted_content_only(
    qapp, migrated_uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch, tmp_path  # noqa: ANN001
) -> None:
    from PySide6.QtWidgets import QFileDialog

    from autotrade.app_ui.controllers.history import HistoryController
    from autotrade.app_ui.views.history_page import HistoryPage

    _seed(migrated_uow)
    out_path = tmp_path / "history_export.csv"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out_path), "CSV files (*.csv)")),
    )

    page = HistoryPage(HistoryController(migrated_uow))
    try:
        page.export_button.click()

        assert out_path.exists()
        with out_path.open(newline="", encoding="utf-8") as fh:
            reader = list(csv.DictReader(fh))
        assert len(reader) == 2
        exported_types = {row["type"] for row in reader}
        assert exported_types == {"ui.tray.pause_l1", "ui.broker_hub.test_connection"}
        # Redacted content only — the placeholder token, never a real secret.
        content = out_path.read_text(encoding="utf-8")
        assert "***REDACTED***" in content
        assert "Exported 2 rows" in page.export_result_label.text()
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_export_csv_cancel_dialog_is_a_no_op(
    qapp, migrated_uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
) -> None:
    from PySide6.QtWidgets import QFileDialog

    from autotrade.app_ui.controllers.history import HistoryController
    from autotrade.app_ui.views.history_page import HistoryPage

    _seed(migrated_uow)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )

    page = HistoryPage(HistoryController(migrated_uow))
    try:
        page.export_button.click()  # user hit Cancel in the save dialog

        assert page.export_result_label.text() == ""
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_main_window_wires_the_history_screen(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.tray import TrayController
    from autotrade.app_ui.views.history_page import HistoryPage
    from autotrade.app_ui.views.main_window import MainWindow

    window = MainWindow(TrayController(migrated_uow))
    try:
        assert window.show_screen("history") is True
        assert isinstance(window.pages.currentWidget(), HistoryPage)
    finally:
        window.deleteLater()
