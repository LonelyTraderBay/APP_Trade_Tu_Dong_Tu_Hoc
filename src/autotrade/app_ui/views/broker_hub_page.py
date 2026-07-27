"""T030–T032 — Broker Hub page: Paper/DEMO cards, Test, Enable (cert gate).

All behaviour lives in `BrokerHubController`; this file only renders its read
model and turns typed refusals (`EnableDemoResult`, `SwitchAccountResult`)
into modals. It must never call `core.*`/SQLAlchemy/ccxt directly — see
`specs/003-d1c-desktop-mvp/contracts/ui-core-boundary.md`.

G1.2/G7 "tự kết nối" credential form (Owner types a DEMO key/secret here
instead of needing `autotrade-headless demo-store-creds` in a terminal):
- Both inputs use `EchoMode.Password` and are cleared immediately after every
  submit attempt (success or failure) — same treatment as
  `settings_page.py`'s PIN/Telegram fields. Once stored, a credential is
  never read back into any widget; only "configured"/"not configured" is
  ever shown (`BrokerHubState.demo_credentials_configured`).
- Test connection / Enable DEMO reuse the existing `setEnabled` +
  `setToolTip` idiom (`can_enable_demo` / `cert_gate_reason`) for the new
  "store credentials first" precondition — see
  `BrokerHubState.demo_ready_for_connection` / `credentials_gate_reason`.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
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

from autotrade.app_ui.controllers.broker_hub import BrokerHubController
from autotrade.app_ui.services.broker_hub import BrokerAccountSummary, BrokerHubState


def _account_text(summary: BrokerAccountSummary | None, *, empty: str) -> str:
    if summary is None:
        return empty
    active = "active" if summary.is_active else "inactive"
    endpoint = summary.endpoint_class or "local"
    return f"{summary.account_id} · {summary.status} · {endpoint} · {active}"


class BrokerHubPage(QWidget):
    """Broker Hub screen: Paper/DEMO cards, Test connection, Enable DEMO."""

    def __init__(
        self, controller: BrokerHubController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("brokerHubPage")
        self._controller = controller

        title = QLabel("Broker Hub")
        title.setObjectName("pageTitle")
        font = title.font()
        font.setPointSize(font.pointSize() + 6)
        font.setBold(True)
        title.setFont(font)

        # --- Paper card ---------------------------------------------------
        self.paper_card = QGroupBox("Paper")
        self.paper_card.setObjectName("paperCard")
        self.paper_status = QLabel("")
        self.paper_status.setObjectName("paperStatus")
        self.paper_status.setWordWrap(True)
        self.switch_paper_button = QPushButton("Switch to Paper")
        self.switch_paper_button.setObjectName("switchPaperButton")
        self.switch_paper_button.clicked.connect(self._on_switch_paper)
        paper_layout = QVBoxLayout(self.paper_card)
        paper_layout.addWidget(self.paper_status)
        paper_layout.addWidget(self.switch_paper_button)

        # --- DEMO card -------------------------------------------------
        self.demo_card = QGroupBox("DEMO")
        self.demo_card.setObjectName("demoCard")
        self.demo_status = QLabel("")
        self.demo_status.setObjectName("demoStatus")
        self.demo_status.setWordWrap(True)
        self.cert_status = QLabel("")
        self.cert_status.setObjectName("certStatus")
        self.cert_status.setWordWrap(True)
        self.test_result = QLabel("")
        self.test_result.setObjectName("testResult")
        self.test_result.setWordWrap(True)

        # --- DEMO credential form (G1.2/G7 "tự kết nối") ------------------
        self.demo_credentials_status_label = QLabel("")
        self.demo_credentials_status_label.setObjectName("demoCredentialsStatusLabel")

        self.demo_api_key_input = QLineEdit()
        self.demo_api_key_input.setObjectName("demoApiKeyInput")
        self.demo_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.demo_api_key_input.setPlaceholderText("DEMO API key")

        self.demo_api_secret_input = QLineEdit()
        self.demo_api_secret_input.setObjectName("demoApiSecretInput")
        self.demo_api_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.demo_api_secret_input.setPlaceholderText("DEMO API secret")

        self.save_demo_credentials_button = QPushButton("Save credentials")
        self.save_demo_credentials_button.setObjectName("saveDemoCredentialsButton")
        self.save_demo_credentials_button.clicked.connect(self._on_save_demo_credentials)

        self.demo_credentials_result_label = QLabel("")
        self.demo_credentials_result_label.setObjectName("demoCredentialsResultLabel")
        self.demo_credentials_result_label.setWordWrap(True)

        credentials_form = QWidget()
        credentials_form_layout = QVBoxLayout(credentials_form)
        credentials_form_layout.setContentsMargins(0, 0, 0, 0)
        credentials_form_layout.addWidget(self.demo_api_key_input)
        credentials_form_layout.addWidget(self.demo_api_secret_input)
        credentials_form_layout.addWidget(self.save_demo_credentials_button)
        credentials_form_layout.addWidget(self.demo_credentials_result_label)

        buttons = QWidget()
        buttons_layout = QHBoxLayout(buttons)
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        self.test_connection_button = QPushButton("Test connection")
        self.test_connection_button.setObjectName("testConnectionButton")
        self.test_connection_button.clicked.connect(self._on_test_connection)

        self.enable_demo_button = QPushButton("Enable DEMO")
        self.enable_demo_button.setObjectName("enableDemoButton")
        self.enable_demo_button.clicked.connect(self._on_enable_demo)

        self.switch_demo_button = QPushButton("Switch to DEMO")
        self.switch_demo_button.setObjectName("switchDemoButton")
        self.switch_demo_button.clicked.connect(self._on_switch_demo)

        self.disable_demo_button = QPushButton("Disconnect / Disable DEMO")
        self.disable_demo_button.setObjectName("disableDemoButton")
        self.disable_demo_button.clicked.connect(self._on_disable_demo)

        buttons_layout.addWidget(self.test_connection_button)
        buttons_layout.addWidget(self.enable_demo_button)
        buttons_layout.addWidget(self.switch_demo_button)
        buttons_layout.addWidget(self.disable_demo_button)

        demo_layout = QVBoxLayout(self.demo_card)
        demo_layout.addWidget(self.demo_status)
        demo_layout.addWidget(self.cert_status)
        demo_layout.addWidget(self.demo_credentials_status_label)
        demo_layout.addWidget(credentials_form)
        demo_layout.addWidget(buttons)
        demo_layout.addWidget(self.test_result)

        cards = QWidget()
        cards_layout = QHBoxLayout(cards)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.addWidget(self.paper_card)
        cards_layout.addWidget(self.demo_card)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(separator)
        layout.addWidget(cards)
        layout.addStretch(1)

        self.refresh()

    # --- state ---------------------------------------------------------

    def refresh(self) -> None:
        """Re-read the controller snapshot and repaint every widget."""
        try:
            state = self._controller.snapshot()
        except Exception as exc:  # noqa: BLE001 - a snapshot must never crash the page
            self.paper_status.setText(f"Session unavailable — {type(exc).__name__}")
            self.demo_status.setText("")
            self.cert_status.setText("")
            self.enable_demo_button.setEnabled(False)
            self.test_connection_button.setEnabled(False)
            return
        self._render(state)

    def _render(self, state: BrokerHubState) -> None:
        self.paper_status.setText(
            _account_text(state.paper_account, empty="No Paper account provisioned yet.")
        )
        self.demo_status.setText(
            _account_text(state.demo_account, empty="No DEMO account provisioned yet.")
        )
        self.cert_status.setText(
            f"Certification: {'VALID' if state.cert_valid else 'NOT VALID'}"
        )
        self.demo_credentials_status_label.setText(
            "DEMO credentials: "
            + ("configured" if state.demo_credentials_configured else "not configured")
        )

        # Test connection / Enable DEMO share one gating idiom: setEnabled +
        # setToolTip. A cert refusal (existing behaviour) takes priority over
        # the new "store credentials first" precondition so the tooltip text
        # operators already rely on doesn't change when cert is invalid.
        if not state.cert_valid:
            enable_tooltip = state.cert_gate_reason
        elif not state.demo_ready_for_connection:
            enable_tooltip = state.credentials_gate_reason
        else:
            enable_tooltip = state.cert_gate_reason
        self.enable_demo_button.setEnabled(
            state.can_enable_demo and state.demo_ready_for_connection
        )
        self.enable_demo_button.setToolTip(enable_tooltip)

        self.test_connection_button.setEnabled(state.demo_ready_for_connection)
        self.test_connection_button.setToolTip(
            "" if state.demo_ready_for_connection else state.credentials_gate_reason
        )

        if state.last_test_at is None:
            self.test_result.setText("No connection test run yet.")
        elif state.last_error_redacted:
            self.test_result.setText(
                f"Last test ({state.last_test_at}) failed [{state.last_verdict}]:"
                f" {state.last_error_redacted}"
            )
        else:
            self.test_result.setText(
                f"Last test ({state.last_test_at}) OK [{state.last_verdict}]:"
                f" {state.capabilities_redacted}"
            )

    # --- actions ---------------------------------------------------------

    def _on_save_demo_credentials(self) -> None:
        api_key = self.demo_api_key_input.text()
        api_secret = self.demo_api_secret_input.text()

        result = self._controller.store_credentials(
            self._controller.demo_account_id, api_key=api_key, api_secret=api_secret
        )

        # Clear both fields immediately after every submit attempt, success
        # or failure — plaintext must never linger in a widget (same rule as
        # settings_page.py's PIN/Telegram fields).
        self.demo_api_key_input.clear()
        self.demo_api_secret_input.clear()

        if result.ok:
            self.demo_credentials_result_label.setText("DEMO credentials saved.")
            self.refresh()
        else:
            self.demo_credentials_result_label.setText(result.error or "Save failed.")
            QMessageBox.warning(self, "Save failed", result.error or "Unknown error.")

    def _on_test_connection(self) -> None:
        result = self._controller.test_connection(mode="DEMO")
        self.refresh()
        if not result.ok:
            QMessageBox.warning(
                self,
                "Connection test failed",
                f"DEMO connection test failed:\n{result.error_redacted}",
            )

    def _on_enable_demo(self) -> None:
        result = self._controller.enable_demo()
        self.refresh()
        if not result.ok:
            QMessageBox.warning(
                self,
                "Enable DEMO refused",
                f"DEMO was not enabled:\n{result.refused_reason}",
            )

    def _on_disable_demo(self) -> None:
        self._controller.disable_demo()
        self.refresh()

    def _on_switch_paper(self) -> None:
        self._switch("paper")

    def _on_switch_demo(self) -> None:
        self._switch("demo")

    def _switch(self, target: str) -> None:
        result = self._controller.switch_account(target)
        self.refresh()
        if not result.ok:
            reason = result.error or ", ".join(result.reasons) or "unknown reason"
            QMessageBox.warning(
                self,
                "Switch account refused",
                f"Could not switch to {target.upper()}:\n{reason}",
            )
