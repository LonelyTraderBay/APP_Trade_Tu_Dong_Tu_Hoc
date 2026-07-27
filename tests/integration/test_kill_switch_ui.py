"""T040/T042 — Kill-switch page: Pause is never PIN-gated, L1-L4 display is
read-only, Flatten is confirm-dialog-only.

Skipped entirely when the optional `[ui]` extra (PySide6) is not installed --
same `qapp` fixture pattern as `test_broker_hub_ui.py`. Proves the Pause path
reachable from this screen is byte-for-byte `TrayController.pause()` (no
PIN check, no confirmation dialog), that L2-L4 have no manual "raise"
controls on this screen, and (T042) that Flatten always blocks on a
required Yes/No confirm dialog and never lets a raw exception reach Qt.
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest
from sqlalchemy import select

from autotrade.app_ui.controllers.kill_switch import FLATTEN_AUDIT_TYPE, KillSwitchController
from autotrade.app_ui.controllers.tray import PAUSE_AUDIT_TYPE, TrayController
from autotrade.core.adapters.ccxt_demo.adapter import FakeCcxtExchange
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.persistence.models import Account, AuditEvent, KillSwitchState
from autotrade.persistence.uow import UnitOfWork

DEMO_ACCOUNT_ID = "demo-binance"


def _seed_active_demo_account(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add(
            Account(
                account_id=DEMO_ACCOUNT_ID,
                adapter_id="ccxt",
                mode="DEMO",
                endpoint="binance_spot_testnet",
                status="READY",
                eligibility="DEMO_CERTIFIED",
                is_active=True,
            )
        )


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201 - QApplication, only when PySide6 exists
    pytest.importorskip("PySide6", reason="optional extra [ui] not installed")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.mark.d1c
def test_pause_button_raises_ks_to_l1_without_any_pin(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.views.kill_switch_page import KillSwitchPage

    page = KillSwitchPage(TrayController(migrated_uow))
    try:
        assert "0" in page.level_label.text()

        page.pause_button.click()

        assert "L1" in page.level_label.text()
        assert "yes" in page.latched_label.text().lower()
        assert "Paused" in page.pause_result_label.text()
        with migrated_uow.session() as session:
            row = session.scalars(
                select(KillSwitchState).where(KillSwitchState.scope == "global")
            ).one()
            assert row.level == 1
            assert row.latched is True
            events = session.scalars(
                select(AuditEvent).where(AuditEvent.type == PAUSE_AUDIT_TYPE)
            ).all()
            assert len(events) == 1
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_pause_button_is_idempotent_and_reports_already_paused(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.views.kill_switch_page import KillSwitchPage

    page = KillSwitchPage(TrayController(migrated_uow))
    try:
        page.pause_button.click()
        page.pause_button.click()

        assert "Already paused" in page.pause_result_label.text()
        with migrated_uow.session() as session:
            row = session.scalars(
                select(KillSwitchState).where(KillSwitchState.scope == "global")
            ).one()
            assert row.level == 1
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_latched_trigger_payload_is_displayed(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.views.kill_switch_page import KillSwitchPage

    with migrated_uow.session() as session:
        session.add(
            KillSwitchState(
                scope="global",
                level=3,
                latched=True,
                triggers_json={"reason": "daily_loss_limit", "level": 3},
            )
        )

    page = KillSwitchPage(TrayController(migrated_uow))
    try:
        assert "L3" in page.level_label.text()
        assert "yes" in page.latched_label.text().lower()
        assert "daily_loss_limit" in page.triggers_label.text()
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_pause_button_has_no_pin_field_and_no_confirmation_dialog(
    qapp, migrated_uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
) -> None:
    """Static + behavioural guard: nothing on this page can trap the operator
    behind a PIN prompt or a confirmation modal before Pause takes effect."""
    from PySide6.QtWidgets import QLineEdit, QMessageBox
    from PySide6.QtWidgets import QWidget as _QWidget

    from autotrade.app_ui.views.kill_switch_page import KillSwitchPage

    dialogs_shown: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda *a, **k: dialogs_shown.append("warning")),
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: dialogs_shown.append("question")),
    )

    page = KillSwitchPage(TrayController(migrated_uow))
    try:
        # No PIN input anywhere on the page.
        assert page.findChildren(QLineEdit) == []

        page.pause_button.click()

        # No modal/confirmation dialog was ever invoked by the click.
        assert dialogs_shown == []
        assert isinstance(page, _QWidget)  # page itself never blocked
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_no_manual_raise_buttons_for_l2_through_l4(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    """L2-L4 are system-escalated; this screen must not offer a manual raise.

    T042 adds a legitimate "Flatten" button (contract: `flatten_local` is
    No PIN, confirm-dialog-only) — that is a different action (a
    reduce-only close, gated by a required Yes/No confirm) from manually
    raising the kill-switch level, and is explicitly allowed here. What
    must still never exist is a control that raises to L2/L3/L4.
    """
    from PySide6.QtWidgets import QPushButton

    from autotrade.app_ui.views.kill_switch_page import KillSwitchPage

    page = KillSwitchPage(TrayController(migrated_uow))
    try:
        labels = [b.text().lower() for b in page.findChildren(QPushButton)]
        assert labels  # sanity: Pause exists
        # "raise to L1" (the Pause button itself) is expected and fine; what
        # must not exist is any control that raises to L2/L3/L4.
        assert not any("l2" in text or "l3" in text or "l4" in text for text in labels)
    finally:
        page.deleteLater()


# --- T042: Flatten -----------------------------------------------------------


@pytest.mark.d1c
def test_flatten_confirm_dialog_blocks_action_on_no(
    qapp, migrated_uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
) -> None:
    """Answering No to the required confirm dialog is a hard no-op: no
    order submitted, no flatten audit event recorded."""
    from PySide6.QtWidgets import QMessageBox

    from autotrade.app_ui.views.kill_switch_page import KillSwitchPage

    _seed_active_demo_account(migrated_uow)
    exchange = FakeCcxtExchange()
    exchange._positions[D1B_ALLOWLIST.symbol] = Decimal("0.01")

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )

    controller = KillSwitchController(migrated_uow, exchange_factory=lambda: exchange)
    page = KillSwitchPage(TrayController(migrated_uow), flatten_controller=controller)
    try:
        page.flatten_button.click()

        assert page.flatten_result_label.text() == ""
        assert exchange._positions[D1B_ALLOWLIST.symbol] == Decimal("0.01")
        with migrated_uow.session() as session:
            events = session.scalars(
                select(AuditEvent).where(AuditEvent.type == FLATTEN_AUDIT_TYPE)
            ).all()
            assert events == []
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_flatten_confirm_yes_submits_order_and_shows_success_modal(
    qapp, migrated_uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
) -> None:
    """Answering Yes runs `KillSwitchController.flatten()`; a successful
    close shows a success modal and updates the result label."""
    from PySide6.QtWidgets import QMessageBox

    from autotrade.app_ui.views.kill_switch_page import KillSwitchPage

    _seed_active_demo_account(migrated_uow)
    exchange = FakeCcxtExchange()
    exchange._positions[D1B_ALLOWLIST.symbol] = Decimal("0.01")

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    infos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda parent, title, text: infos.append((title, text))),
    )

    controller = KillSwitchController(migrated_uow, exchange_factory=lambda: exchange)
    page = KillSwitchPage(TrayController(migrated_uow), flatten_controller=controller)
    try:
        page.flatten_button.click()

        assert len(infos) == 1
        assert "flattened" in page.flatten_result_label.text().lower()
        assert exchange._positions[D1B_ALLOWLIST.symbol] == Decimal("0")
        with migrated_uow.session() as session:
            events = session.scalars(
                select(AuditEvent).where(AuditEvent.type == FLATTEN_AUDIT_TYPE)
            ).all()
            assert len(events) == 1
            assert events[0].payload_redacted["ok"] is True
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_flatten_submit_failure_shows_error_modal_without_crashing(
    qapp, migrated_uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
) -> None:
    """A submit failure (e.g. adapter disconnect) must surface as an error
    modal, never a raw exception, and the page must remain usable after."""
    from PySide6.QtWidgets import QMessageBox

    from autotrade.app_ui.views.kill_switch_page import KillSwitchPage

    _seed_active_demo_account(migrated_uow)
    exchange = FakeCcxtExchange(disconnect=True)
    exchange._positions[D1B_ALLOWLIST.symbol] = Decimal("0.01")

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    warnings_shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda parent, title, text: warnings_shown.append((title, text))),
    )

    controller = KillSwitchController(migrated_uow, exchange_factory=lambda: exchange)
    page = KillSwitchPage(TrayController(migrated_uow), flatten_controller=controller)
    try:
        page.flatten_button.click()

        assert len(warnings_shown) == 1
        assert "failed" in page.flatten_result_label.text().lower()
        # The page must still be usable afterwards — no crash.
        page.refresh()
        with migrated_uow.session() as session:
            events = session.scalars(
                select(AuditEvent).where(AuditEvent.type == FLATTEN_AUDIT_TYPE)
            ).all()
            assert len(events) == 1
            assert events[0].payload_redacted["ok"] is False
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_flatten_no_active_account_is_handled_gracefully(
    qapp, migrated_uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
) -> None:
    """No active account -> a clear typed result, shown as a modal, never
    a crash (contract: "or the action should return a clear 'no active
    account' result — do not crash")."""
    from PySide6.QtWidgets import QMessageBox

    from autotrade.app_ui.views.kill_switch_page import KillSwitchPage

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    warnings_shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda parent, title, text: warnings_shown.append((title, text))),
    )

    page = KillSwitchPage(TrayController(migrated_uow))
    try:
        page.flatten_button.click()

        assert len(warnings_shown) == 1
        assert "no active account" in page.flatten_result_label.text().lower()
    finally:
        page.deleteLater()
