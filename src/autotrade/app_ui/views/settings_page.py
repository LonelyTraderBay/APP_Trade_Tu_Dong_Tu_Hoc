"""T052/T053 — Settings page: PIN, Telegram, allowlist (read-only), backup,
restore (FR-005), autostart.

One `QGroupBox` per concern, matching `kill_switch_page.py`'s established
card style. Every mutating action goes through `SettingsController` — this
file never imports `core`/`persistence`/SQLAlchemy/keyring/winreg directly.

Hard safety invariants enforced here:
- The PIN `QLineEdit`s use `EchoMode.Password` and are cleared immediately
  after every submit attempt (success or failure) — the plaintext PIN is
  never logged, never left sitting in a widget longer than necessary, and
  this file never calls `print`/logging on their contents.
- The Telegram bot-token field is also `EchoMode.Password`. Once a token is
  stored, it is never read back into any widget — the status label only
  ever shows "configured" / "not configured", never the value.
- The allowlist card is built entirely from `QLabel`s — no editable widget
  exists for it, ever (`core/domain/allowlist.py`'s own docstring: Owner-
  locked immutable data).
- Restore is genuinely destructive (overwrites the live trading database),
  so it follows `kill_switch_page.py`'s Flatten idiom exactly: a REQUIRED
  Yes/No confirm dialog, default answer No, and answering anything but Yes
  is a hard no-op — no controller call, no file touched.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from autotrade.app_ui.controllers.settings import SettingsController
from autotrade.app_ui.services.settings import SettingsView

RESTORE_CONFIRM_TEXT = (
    "This will overwrite the current database with the selected backup file. "
    "A safety backup of the CURRENT database will be taken first, so this can "
    "be undone by restoring that safety backup — but the restore you are about "
    "to run cannot be undone from within the app. Continue?"
)


class SettingsPage(QWidget):
    """Settings screen: PIN change, optional Telegram, allowlist, backup, autostart."""

    def __init__(
        self, controller: SettingsController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self._controller = controller

        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        font = title.font()
        font.setPointSize(font.pointSize() + 6)
        font.setBold(True)
        title.setFont(font)

        pin_card = self._build_pin_card()
        telegram_card = self._build_telegram_card()
        allowlist_card = self._build_allowlist_card()
        backup_card = self._build_backup_card()
        autostart_card = self._build_autostart_card()

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(separator)
        layout.addWidget(pin_card)
        layout.addWidget(telegram_card)
        layout.addWidget(allowlist_card)
        layout.addWidget(backup_card)
        layout.addWidget(autostart_card)
        layout.addStretch(1)

        self.refresh()

    # --- card builders ---------------------------------------------------

    def _build_pin_card(self) -> QGroupBox:
        card = QGroupBox("PIN")
        card.setObjectName("pinCard")

        self.pin_status_label = QLabel("")
        self.pin_status_label.setObjectName("pinStatusLabel")

        self.current_pin_input = QLineEdit()
        self.current_pin_input.setObjectName("currentPinInput")
        self.current_pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.current_pin_input.setPlaceholderText("Current PIN (leave blank if none set)")

        self.new_pin_input = QLineEdit()
        self.new_pin_input.setObjectName("newPinInput")
        self.new_pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_pin_input.setPlaceholderText("New PIN")

        self.confirm_pin_input = QLineEdit()
        self.confirm_pin_input.setObjectName("confirmPinInput")
        self.confirm_pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_pin_input.setPlaceholderText("Confirm new PIN")

        self.change_pin_button = QPushButton("Change PIN")
        self.change_pin_button.setObjectName("changePinButton")
        self.change_pin_button.clicked.connect(self._on_change_pin)

        self.pin_result_label = QLabel("")
        self.pin_result_label.setObjectName("pinResultLabel")
        self.pin_result_label.setWordWrap(True)

        layout = QVBoxLayout(card)
        layout.addWidget(self.pin_status_label)
        layout.addWidget(self.current_pin_input)
        layout.addWidget(self.new_pin_input)
        layout.addWidget(self.confirm_pin_input)
        layout.addWidget(self.change_pin_button)
        layout.addWidget(self.pin_result_label)
        return card

    def _build_telegram_card(self) -> QGroupBox:
        card = QGroupBox("Telegram (optional)")
        card.setObjectName("telegramCard")

        self.telegram_status_label = QLabel("")
        self.telegram_status_label.setObjectName("telegramStatusLabel")

        self.telegram_token_input = QLineEdit()
        self.telegram_token_input.setObjectName("telegramTokenInput")
        self.telegram_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.telegram_token_input.setPlaceholderText("Bot token")

        self.telegram_chat_input = QLineEdit()
        self.telegram_chat_input.setObjectName("telegramChatInput")
        self.telegram_chat_input.setPlaceholderText("Chat id")

        buttons = QWidget()
        buttons_layout = QHBoxLayout(buttons)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.save_telegram_button = QPushButton("Save")
        self.save_telegram_button.setObjectName("saveTelegramButton")
        self.save_telegram_button.clicked.connect(self._on_save_telegram)
        self.clear_telegram_button = QPushButton("Clear")
        self.clear_telegram_button.setObjectName("clearTelegramButton")
        self.clear_telegram_button.clicked.connect(self._on_clear_telegram)
        self.test_telegram_button = QPushButton("Send test message")
        self.test_telegram_button.setObjectName("testTelegramButton")
        self.test_telegram_button.clicked.connect(self._on_test_telegram)
        buttons_layout.addWidget(self.save_telegram_button)
        buttons_layout.addWidget(self.clear_telegram_button)
        buttons_layout.addWidget(self.test_telegram_button)

        self.telegram_result_label = QLabel("")
        self.telegram_result_label.setObjectName("telegramResultLabel")
        self.telegram_result_label.setWordWrap(True)

        layout = QVBoxLayout(card)
        layout.addWidget(self.telegram_status_label)
        layout.addWidget(self.telegram_token_input)
        layout.addWidget(self.telegram_chat_input)
        layout.addWidget(buttons)
        layout.addWidget(self.telegram_result_label)
        return card

    def _build_allowlist_card(self) -> QGroupBox:
        card = QGroupBox("Allowlist (Owner-locked, read-only)")
        card.setObjectName("allowlistCard")

        self.allowlist_exchange_label = QLabel("")
        self.allowlist_exchange_label.setObjectName("allowlistExchangeLabel")
        self.allowlist_market_label = QLabel("")
        self.allowlist_market_label.setObjectName("allowlistMarketLabel")
        self.allowlist_endpoint_label = QLabel("")
        self.allowlist_endpoint_label.setObjectName("allowlistEndpointLabel")
        self.allowlist_symbol_label = QLabel("")
        self.allowlist_symbol_label.setObjectName("allowlistSymbolLabel")
        self.allowlist_timeframe_label = QLabel("")
        self.allowlist_timeframe_label.setObjectName("allowlistTimeframeLabel")

        layout = QVBoxLayout(card)
        layout.addWidget(self.allowlist_exchange_label)
        layout.addWidget(self.allowlist_market_label)
        layout.addWidget(self.allowlist_endpoint_label)
        layout.addWidget(self.allowlist_symbol_label)
        layout.addWidget(self.allowlist_timeframe_label)
        return card

    def _build_backup_card(self) -> QGroupBox:
        card = QGroupBox("Backup")
        card.setObjectName("backupCard")

        self.backup_button = QPushButton("Backup now")
        self.backup_button.setObjectName("backupButton")
        self.backup_button.clicked.connect(self._on_backup)

        self.backup_result_label = QLabel("")
        self.backup_result_label.setObjectName("backupResultLabel")
        self.backup_result_label.setWordWrap(True)

        self.restore_button = QPushButton("Restore from backup...")
        self.restore_button.setObjectName("restoreButton")
        self.restore_button.clicked.connect(self._on_restore)

        self.restore_result_label = QLabel("")
        self.restore_result_label.setObjectName("restoreResultLabel")
        self.restore_result_label.setWordWrap(True)

        layout = QVBoxLayout(card)
        layout.addWidget(self.backup_button)
        layout.addWidget(self.backup_result_label)
        layout.addWidget(self.restore_button)
        layout.addWidget(self.restore_result_label)
        return card

    def _build_autostart_card(self) -> QGroupBox:
        card = QGroupBox("Autostart")
        card.setObjectName("autostartCard")

        self.autostart_checkbox = QCheckBox("Start AutoTrade AI when Windows starts")
        self.autostart_checkbox.setObjectName("autostartCheckbox")
        self.autostart_checkbox.toggled.connect(self._on_autostart_toggled)

        self.autostart_result_label = QLabel("")
        self.autostart_result_label.setObjectName("autostartResultLabel")
        self.autostart_result_label.setWordWrap(True)

        layout = QVBoxLayout(card)
        layout.addWidget(self.autostart_checkbox)
        layout.addWidget(self.autostart_result_label)
        return card

    # --- state -----------------------------------------------------------

    def refresh(self) -> None:
        """Re-read the controller snapshot and repaint every widget."""
        try:
            view = self._controller.snapshot()
        except Exception as exc:  # noqa: BLE001 - a snapshot must never crash the page
            self.pin_status_label.setText(f"Session unavailable — {type(exc).__name__}")
            return
        self._render(view)

    def _render(self, view: SettingsView) -> None:
        self.pin_status_label.setText(
            f"PIN: {'set' if view.pin_configured else 'not set'}"
        )
        self.current_pin_input.setVisible(view.pin_configured)

        self.telegram_status_label.setText(
            f"Telegram: {'configured' if view.telegram_configured else 'not configured'}"
        )

        allowlist = view.allowlist
        self.allowlist_exchange_label.setText(f"Exchange: {allowlist.exchange_id}")
        self.allowlist_market_label.setText(f"Market: {allowlist.market}")
        self.allowlist_endpoint_label.setText(f"Endpoint class: {allowlist.endpoint_class}")
        self.allowlist_symbol_label.setText(f"Symbol: {allowlist.symbol}")
        self.allowlist_timeframe_label.setText(f"Timeframe: {allowlist.timeframe}")

        self.autostart_checkbox.blockSignals(True)
        self.autostart_checkbox.setChecked(view.autostart_enabled)
        self.autostart_checkbox.blockSignals(False)

    # --- actions: PIN ------------------------------------------------------

    def _on_change_pin(self) -> None:
        current_pin = self.current_pin_input.text()
        new_pin = self.new_pin_input.text()
        confirm_pin = self.confirm_pin_input.text()

        result = self._controller.set_pin(
            current_pin=current_pin, new_pin=new_pin, confirm_pin=confirm_pin
        )

        # Clear every PIN field immediately after the attempt, success or
        # failure — plaintext must never linger in a widget.
        self.current_pin_input.clear()
        self.new_pin_input.clear()
        self.confirm_pin_input.clear()

        if result.ok:
            self.pin_result_label.setText("PIN updated.")
            self.refresh()
        else:
            self.pin_result_label.setText(result.error or "PIN change failed.")
            QMessageBox.warning(self, "PIN change failed", result.error or "Unknown error.")

    # --- actions: Telegram ---------------------------------------------------

    def _on_save_telegram(self) -> None:
        bot_token = self.telegram_token_input.text()
        chat_id = self.telegram_chat_input.text()
        result = self._controller.store_telegram(bot_token=bot_token, chat_id=chat_id)

        # Never leave the token sitting in the widget once the attempt is done.
        self.telegram_token_input.clear()
        self.telegram_chat_input.clear()

        if result.ok:
            self.telegram_result_label.setText("Telegram credentials saved.")
            self.refresh()
        else:
            self.telegram_result_label.setText(result.error or "Save failed.")
            QMessageBox.warning(self, "Save failed", result.error or "Unknown error.")

    def _on_clear_telegram(self) -> None:
        self._controller.clear_telegram()
        self.telegram_result_label.setText("Telegram credentials cleared.")
        self.refresh()

    def _on_test_telegram(self) -> None:
        result = self._controller.send_test_telegram()
        self.telegram_result_label.setText(result.message)

    # --- actions: Backup -----------------------------------------------------

    def _on_backup(self) -> None:
        result = self._controller.run_backup()
        if result.ok:
            self.backup_result_label.setText(f"Backup written to {result.path}")
        else:
            self.backup_result_label.setText(f"Backup failed: {result.error}")
            QMessageBox.warning(self, "Backup failed", result.error or "Unknown error.")

    # --- actions: Restore (FR-005) --------------------------------------------

    def _on_restore(self) -> None:
        """Genuinely destructive: overwrites the live trading database.

        File picker (scoped to the backups directory) -> REQUIRED Yes/No
        confirm (default No, exact idiom as Kill-switch's Flatten) ->
        `SettingsController.run_restore`. Answering anything but Yes, or
        cancelling the file picker, is a hard no-op — no controller call.
        """
        backups_dir = self._controller.default_backups_dir()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select backup file", str(backups_dir), "SQLite backups (*.sqlite3)"
        )
        if not file_path:
            return

        answer = QMessageBox.question(
            self,
            "Confirm restore",
            RESTORE_CONFIRM_TEXT,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self._controller.run_restore(Path(file_path))
        except Exception as exc:  # noqa: BLE001 - a restore must never crash the page
            self.restore_result_label.setText(f"Restore unavailable — {type(exc).__name__}")
            QMessageBox.critical(self, "Restore failed", f"Unexpected error: {exc}")
            return

        self.restore_result_label.setText(result.message)
        if result.ok:
            QMessageBox.information(self, "Restore complete", result.message)
        else:
            QMessageBox.warning(self, "Restore failed", result.message)

    # --- actions: Autostart --------------------------------------------------

    def _on_autostart_toggled(self, checked: bool) -> None:
        result = self._controller.set_autostart(checked)
        if result.ok:
            self.autostart_result_label.setText(
                "Autostart enabled." if result.enabled else "Autostart disabled."
            )
        else:
            self.autostart_result_label.setText(f"Autostart change failed: {result.error}")
            QMessageBox.warning(
                self, "Autostart change failed", result.error or "Unknown error."
            )
            # Reflect the real (unchanged) persisted state, not the failed toggle.
            self.autostart_checkbox.blockSignals(True)
            self.autostart_checkbox.setChecked(result.enabled)
            self.autostart_checkbox.blockSignals(False)
