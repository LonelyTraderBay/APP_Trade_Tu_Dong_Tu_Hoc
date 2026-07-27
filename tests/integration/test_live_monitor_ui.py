"""T041 — Live Monitor page: in-flight rows are marked and never dropped,
truncation is always surfaced, and there is no blind-retry control.

Skipped entirely when the optional `[ui]` extra (PySide6) is not installed --
same `qapp` fixture pattern as `test_broker_hub_ui.py`.
"""

from __future__ import annotations

import os

import pytest

from autotrade.app_ui.controllers.live_monitor import LiveMonitorController
from autotrade.core.domain.money import d
from autotrade.core.oms.fsm import IntentState
from autotrade.persistence.models import Account, OrderIntent
from autotrade.persistence.uow import UnitOfWork


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201 - QApplication, only when PySide6 exists
    pytest.importorskip("PySide6", reason="optional extra [ui] not installed")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _seed_account(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add(
            Account(
                account_id="paper1",
                adapter_id="paper",
                mode="PAPER",
                endpoint="local",
                status="READY",
                eligibility="ELIGIBLE",
                is_active=True,
            )
        )


def _seed_intents(uow: UnitOfWork, *, settled: int, inflight: int) -> None:
    with uow.session() as session:
        for i in range(settled):
            session.add(
                OrderIntent(
                    intent_id=f"s{i:04d}",
                    client_order_id=f"cs{i:04d}",
                    state=IntentState.FILLED.value,
                    account_id="paper1",
                    side="buy",
                    qty=d("1"),
                    symbol="BTC/USDT",
                )
            )
        for i in range(inflight):
            session.add(
                OrderIntent(
                    intent_id=f"u{i:04d}",
                    client_order_id=f"cu{i:04d}",
                    state=IntentState.UNKNOWN.value,
                    account_id="paper1",
                    side="sell",
                    qty=d("2"),
                    symbol="BTC/USDT",
                )
            )


@pytest.mark.d1c
def test_inflight_rows_are_marked_and_never_dropped_by_truncation(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.views.live_monitor_page import ATTENTION_MARKER, LiveMonitorPage

    _seed_account(migrated_uow)
    _seed_intents(migrated_uow, settled=250, inflight=10)

    controller = LiveMonitorController(migrated_uow, account_id="paper1")
    page = LiveMonitorPage(controller)
    try:
        page.limit_spin.setValue(200)
        page.refresh()

        # limit caps the *page*, not the in-flight rows: 260 total intents,
        # 200-row page still carries all 10 in-flight (never sacrificed) plus
        # 190 settled, leaving 60 settled rows truncated.
        assert page.table.rowCount() == 200
        markers = [page.table.item(row, 0).text() for row in range(page.table.rowCount())]
        assert markers.count(ATTENTION_MARKER) == 10
        assert "60 more settled rows not shown" in page.truncated_label.text()
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_truncated_label_reads_showing_all_when_nothing_is_cut(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.views.live_monitor_page import LiveMonitorPage

    _seed_account(migrated_uow)
    _seed_intents(migrated_uow, settled=3, inflight=0)

    page = LiveMonitorPage(LiveMonitorController(migrated_uow, account_id="paper1"))
    try:
        assert page.table.rowCount() == 3
        assert "Showing all 3" in page.truncated_label.text()
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_refresh_button_refetches_the_page(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.views.live_monitor_page import LiveMonitorPage

    _seed_account(migrated_uow)
    page = LiveMonitorPage(LiveMonitorController(migrated_uow, account_id="paper1"))
    try:
        assert page.table.rowCount() == 0

        _seed_intents(migrated_uow, settled=1, inflight=0)
        page.refresh_button.click()

        assert page.table.rowCount() == 1
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_created_at_column_is_populated(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.views.live_monitor_page import LiveMonitorPage

    _seed_account(migrated_uow)
    _seed_intents(migrated_uow, settled=1, inflight=0)

    page = LiveMonitorPage(LiveMonitorController(migrated_uow, account_id="paper1"))
    try:
        created_at_col = page.table.columnCount() - 1
        text = page.table.item(0, created_at_col).text()
        assert text != ""
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_no_blind_retry_or_resubmit_control_exists(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    """Explicit, deliberate omission per tasks.md: read-only display only."""
    from PySide6.QtWidgets import QPushButton

    from autotrade.app_ui.views.live_monitor_page import LiveMonitorPage

    _seed_account(migrated_uow)
    _seed_intents(migrated_uow, settled=1, inflight=1)

    page = LiveMonitorPage(LiveMonitorController(migrated_uow, account_id="paper1"))
    try:
        labels = [b.text().lower() for b in page.findChildren(QPushButton)]
        assert labels  # sanity: Refresh exists
        assert not any("retry" in text for text in labels)
        assert not any("resubmit" in text for text in labels)
        assert not any("resend" in text for text in labels)
        assert not any("cancel" in text for text in labels)
        assert not any("flatten" in text for text in labels)
        # Table itself must never be directly editable (no inline retry-via-edit).
        from PySide6.QtWidgets import QAbstractItemView

        assert (
            page.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
        )
    finally:
        page.deleteLater()
