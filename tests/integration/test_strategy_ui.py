"""T050 — Strategy page: read-only display, zero editable widgets.

Skipped entirely when the optional `[ui]` extra (PySide6) is not installed --
same `qapp` fixture pattern as `test_broker_hub_ui.py`. Proves the page is
built entirely from `QLabel`s (no widget that could be mistaken for an
editable param field) and that `MainWindow` wires it in for the `"strategy"`
screen key.
"""

from __future__ import annotations

import os

import pytest

from autotrade.core.accounts.bindings import bind_demo_strategy
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.persistence.uow import UnitOfWork


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201 - QApplication, only when PySide6 exists
    pytest.importorskip("PySide6", reason="optional extra [ui] not installed")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.mark.d1c
def test_strategy_page_has_zero_editable_widgets(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    """Static guard: no `QLineEdit`/`QComboBox`/`QCheckBox`/`QSpinBox`/
    `QTextEdit`/`QAbstractSpinBox` anywhere on this page — "read-only" is
    explicit in the task name, and the hard ceilings must never look
    editable, even as a disabled widget."""
    from PySide6.QtWidgets import (
        QAbstractSpinBox,
        QCheckBox,
        QComboBox,
        QDateEdit,
        QLineEdit,
        QPlainTextEdit,
        QTextEdit,
    )

    from autotrade.app_ui.controllers.strategy import StrategyController
    from autotrade.app_ui.views.strategy_page import StrategyPage

    page = StrategyPage(StrategyController(migrated_uow))
    try:
        editable_types = (
            QLineEdit,
            QComboBox,
            QCheckBox,
            QAbstractSpinBox,
            QDateEdit,
            QTextEdit,
            QPlainTextEdit,
        )
        for editable_type in editable_types:
            assert page.findChildren(editable_type) == [], editable_type
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_strategy_page_shows_allowlist_defaults_without_a_binding(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.strategy import StrategyController
    from autotrade.app_ui.views.strategy_page import StrategyPage

    page = StrategyPage(StrategyController(migrated_uow))
    try:
        assert D1B_ALLOWLIST.symbol in page.symbol_label.text()
        assert D1B_ALLOWLIST.timeframe in page.timeframe_label.text()
        assert "no" in page.enabled_label.text().lower()
        assert page.binding_status_label.text() != ""
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_strategy_page_shows_a_persisted_binding(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    with migrated_uow.session() as session:
        bind_demo_strategy(session, account_id="demo-binance")

    from autotrade.app_ui.controllers.strategy import StrategyController
    from autotrade.app_ui.views.strategy_page import StrategyPage

    page = StrategyPage(StrategyController(migrated_uow))
    try:
        assert "yes" in page.enabled_label.text().lower()
        assert page.binding_status_label.text() == ""
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_strategy_page_always_shows_the_hard_ceilings(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.strategy import StrategyController
    from autotrade.app_ui.views.strategy_page import StrategyPage

    page = StrategyPage(StrategyController(migrated_uow))
    try:
        assert D1B_ALLOWLIST.exchange_id in page.ceiling_exchange_label.text()
        assert D1B_ALLOWLIST.market in page.ceiling_market_label.text()
        assert D1B_ALLOWLIST.endpoint_class in page.ceiling_endpoint_label.text()
        assert D1B_ALLOWLIST.symbol in page.ceiling_symbol_label.text()
        assert D1B_ALLOWLIST.timeframe in page.ceiling_timeframe_label.text()
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_main_window_wires_the_strategy_screen(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.tray import TrayController
    from autotrade.app_ui.views.main_window import MainWindow
    from autotrade.app_ui.views.strategy_page import StrategyPage

    window = MainWindow(TrayController(migrated_uow))
    try:
        assert window.show_screen("strategy") is True
        assert isinstance(window.pages.currentWidget(), StrategyPage)
    finally:
        window.deleteLater()
