"""T052/T053 — Settings page: PIN, Telegram, allowlist, backup, autostart
through the real UI.

Skipped entirely when the optional `[ui]` extra (PySide6) is not installed --
same `qapp` fixture pattern as `test_broker_hub_ui.py`. `keyring` and
`winreg` are both mocked (same fakes as `test_settings_controller.py` /
`test_autostart.py`) so this suite never touches the real OS credential
store or the real per-user registry.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from autotrade.app_ui.services import autostart as autostart_service
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.persistence.uow import UnitOfWork

from ..unit.test_autostart import FakeWinreg
from ..unit.test_settings_controller import FakeKeyring


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201 - QApplication, only when PySide6 exists
    pytest.importorskip("PySide6", reason="optional extra [ui] not installed")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def fake_keyring(monkeypatch: pytest.MonkeyPatch) -> FakeKeyring:
    fake = FakeKeyring()
    monkeypatch.setattr("autotrade.persistence.secrets.keyring", fake)
    return fake


@pytest.fixture()
def fake_winreg(monkeypatch: pytest.MonkeyPatch) -> FakeWinreg:
    fake = FakeWinreg()
    monkeypatch.setattr(autostart_service, "winreg", fake)
    return fake


# --- PIN -------------------------------------------------------------------


@pytest.mark.d1c
def test_pin_set_then_change_round_trip_through_the_real_ui(
    qapp, migrated_uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
) -> None:
    from PySide6.QtWidgets import QMessageBox

    from autotrade.app_ui.controllers.settings import SettingsController
    from autotrade.app_ui.views.settings_page import SettingsPage

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda parent, title, text: warnings.append((title, text))),
    )

    page = SettingsPage(SettingsController(migrated_uow))
    try:
        assert "not set" in page.pin_status_label.text().lower()

        # First set (no current PIN exists yet).
        page.new_pin_input.setText("1234")
        page.confirm_pin_input.setText("1234")
        page.change_pin_button.click()

        assert warnings == []
        assert "set" in page.pin_status_label.text().lower()
        assert "not set" not in page.pin_status_label.text().lower()
        # Plaintext must never linger in the widgets after the attempt.
        assert page.new_pin_input.text() == ""
        assert page.confirm_pin_input.text() == ""

        # Wrong current PIN is refused with a modal, PIN unchanged.
        page.current_pin_input.setText("0000")
        page.new_pin_input.setText("5678")
        page.confirm_pin_input.setText("5678")
        page.change_pin_button.click()

        assert len(warnings) == 1
        assert "incorrect" in warnings[0][1].lower()
        assert page.current_pin_input.text() == ""

        # Matching current PIN succeeds.
        page.current_pin_input.setText("1234")
        page.new_pin_input.setText("5678")
        page.confirm_pin_input.setText("5678")
        page.change_pin_button.click()

        assert len(warnings) == 1  # no new warning
        assert "updated" in page.pin_result_label.text().lower()
    finally:
        page.deleteLater()


# --- Telegram ----------------------------------------------------------------


@pytest.mark.d1c
def test_telegram_store_and_clear_never_displays_the_token(
    qapp, migrated_uow: UnitOfWork, fake_keyring: FakeKeyring  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.settings import SettingsController
    from autotrade.app_ui.views.settings_page import SettingsPage

    page = SettingsPage(SettingsController(migrated_uow))
    try:
        assert "not configured" in page.telegram_status_label.text().lower()

        page.telegram_token_input.setText("super-secret-bot-token")
        page.telegram_chat_input.setText("chat-123")
        page.save_telegram_button.click()

        assert "configured" in page.telegram_status_label.text().lower()
        assert "not configured" not in page.telegram_status_label.text().lower()
        # The widget must be cleared, and the token must never reappear
        # anywhere in the page's rendered text.
        assert page.telegram_token_input.text() == ""
        assert "super-secret-bot-token" not in page.telegram_result_label.text()
        assert ("AutoTradeAI", "telegram:bot_token") in fake_keyring._store

        page.clear_telegram_button.click()

        assert "not configured" in page.telegram_status_label.text().lower()
        assert ("AutoTradeAI", "telegram:bot_token") not in fake_keyring._store
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_telegram_send_test_message_uses_fake_sender(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.settings import SettingsController
    from autotrade.app_ui.views.settings_page import SettingsPage

    page = SettingsPage(SettingsController(migrated_uow))
    try:
        page.test_telegram_button.click()

        assert "fake sender" in page.telegram_result_label.text().lower()
    finally:
        page.deleteLater()


# --- Allowlist (read-only) ---------------------------------------------------


@pytest.mark.d1c
def test_allowlist_fields_are_plain_non_editable_labels(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from PySide6.QtWidgets import QLabel

    from autotrade.app_ui.controllers.settings import SettingsController
    from autotrade.app_ui.views.settings_page import SettingsPage

    page = SettingsPage(SettingsController(migrated_uow))
    try:
        assert isinstance(page.allowlist_exchange_label, QLabel)
        assert D1B_ALLOWLIST.exchange_id in page.allowlist_exchange_label.text()
        assert D1B_ALLOWLIST.market in page.allowlist_market_label.text()
        assert D1B_ALLOWLIST.endpoint_class in page.allowlist_endpoint_label.text()
        assert D1B_ALLOWLIST.symbol in page.allowlist_symbol_label.text()
        assert D1B_ALLOWLIST.timeframe in page.allowlist_timeframe_label.text()
        # No editable widget exists inside the allowlist card itself.
        from PySide6.QtWidgets import QLineEdit

        assert page.findChild(QLineEdit, "allowlistExchangeLabel") is None
    finally:
        page.deleteLater()


# --- Backup ------------------------------------------------------------------


@pytest.mark.d1c
def test_backup_button_calls_snapshot_database_and_shows_the_result_path(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    """`migrated_uow` already points `AUTOTRADE_DATA_DIR` at a pytest
    tmp_path (see conftest.py), so the default `db_path` this button uses
    is never a real machine data directory."""
    from autotrade.app_ui.controllers.settings import SettingsController
    from autotrade.app_ui.views.settings_page import SettingsPage
    from autotrade.persistence.engine import default_db_path

    assert default_db_path().exists()  # sanity: migrated_uow already created it

    page = SettingsPage(SettingsController(migrated_uow))
    try:
        page.backup_button.click()

        assert "Backup written to" in page.backup_result_label.text()
        assert "backups" in page.backup_result_label.text()
    finally:
        page.deleteLater()


# --- Autostart (T053) ---------------------------------------------------------


@pytest.mark.d1c
def test_autostart_checkbox_reflects_and_toggles_persisted_state(
    qapp, migrated_uow: UnitOfWork, fake_winreg: FakeWinreg  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.settings import SettingsController
    from autotrade.app_ui.views.settings_page import SettingsPage

    page = SettingsPage(SettingsController(migrated_uow))
    try:
        assert page.autostart_checkbox.isChecked() is False

        page.autostart_checkbox.setChecked(True)

        assert "enabled" in page.autostart_result_label.text().lower()
        assert autostart_service.VALUE_NAME in fake_winreg.values

        # A fresh page re-reads the persisted preference (not stale UI state).
        page2 = SettingsPage(SettingsController(migrated_uow))
        try:
            assert page2.autostart_checkbox.isChecked() is True
        finally:
            page2.deleteLater()

        page.autostart_checkbox.setChecked(False)

        assert "disabled" in page.autostart_result_label.text().lower()
        assert autostart_service.VALUE_NAME not in fake_winreg.values
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_autostart_toggle_failure_shows_a_warning_and_reverts_the_checkbox(
    qapp, migrated_uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch  # noqa: ANN001
) -> None:
    from PySide6.QtWidgets import QMessageBox

    from autotrade.app_ui.controllers.settings import SettingsController
    from autotrade.app_ui.views.settings_page import SettingsPage

    def _boom(*args: Any, **kwargs: Any) -> None:
        raise OSError("access denied")

    monkeypatch.setattr(autostart_service, "set_autostart", _boom)
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda parent, title, text: warnings.append((title, text))),
    )

    page = SettingsPage(SettingsController(migrated_uow))
    try:
        page.autostart_checkbox.setChecked(True)

        assert len(warnings) == 1
        assert page.autostart_checkbox.isChecked() is False
    finally:
        page.deleteLater()


# --- Wiring ------------------------------------------------------------------


@pytest.mark.d1c
def test_main_window_wires_the_settings_screen(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.tray import TrayController
    from autotrade.app_ui.views.main_window import MainWindow
    from autotrade.app_ui.views.settings_page import SettingsPage

    window = MainWindow(TrayController(migrated_uow))
    try:
        assert window.show_screen("settings") is True
        assert isinstance(window.pages.currentWidget(), SettingsPage)
    finally:
        window.deleteLater()
