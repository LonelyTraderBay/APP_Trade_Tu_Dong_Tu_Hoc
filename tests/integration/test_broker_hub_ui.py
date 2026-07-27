"""T033 — Broker Hub Qt wiring: MainWindow -> BrokerHubPage -> BrokerHubController.

Skipped entirely when the optional `[ui]` extra (PySide6) is not installed --
same `qapp` fixture pattern as `tests/unit/test_ui_shell.py`. Proves the
refusal paths from the contract (`CertificationNotValid`, `SwitchRejected`)
reach the operator as a modal and never as a raw exception or a silent no-op.

`fake_keyring` (autouse) mirrors `test_settings_ui.py` / `test_settings_controller.py`'s
in-memory `FakeKeyring` stand-in. It has to be autouse here — unlike
Settings, every `BrokerHubPage(...)` construction calls `refresh()` in
`__init__`, which calls `BrokerHubController.snapshot()`, which (as of the
G1.2/G7 credential form) now calls `demo_credentials_configured()` and reads
the keyring. Before this task, `test_broker_hub_ui.py` never touched
keyring/`persistence.secrets` at all; this fixture keeps this suite hitting
only an in-memory fake instead of a real OS credential store.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from autotrade.app_ui.controllers.broker_hub import DEFAULT_PAPER_ACCOUNT_ID
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.persistence.models import Account, CertificationRecord, ReconBreak
from autotrade.persistence.uow import UnitOfWork

from ..unit.test_settings_controller import FakeKeyring

DEMO_ACCOUNT_ID = "demo-binance"


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201 - QApplication, only when PySide6 exists
    pytest.importorskip("PySide6", reason="optional extra [ui] not installed")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def fake_keyring(monkeypatch: pytest.MonkeyPatch) -> FakeKeyring:
    fake = FakeKeyring()
    monkeypatch.setattr("autotrade.persistence.secrets.keyring", fake)
    return fake


@pytest.fixture()
def warnings(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Capture every `QMessageBox.warning(...)` call instead of blocking on it."""
    from PySide6.QtWidgets import QMessageBox

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda parent, title, text: calls.append((title, text))),
    )
    return calls


def _seed_demo_credentials(fake_keyring: FakeKeyring, account_id: str = DEMO_ACCOUNT_ID) -> None:
    fake_keyring.set_password("AutoTradeAI", f"{account_id}:api_key", "seed-key")
    fake_keyring.set_password("AutoTradeAI", f"{account_id}:api_secret", "seed-secret")


def _seed_paper_active(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add(
            Account(
                account_id=DEFAULT_PAPER_ACCOUNT_ID,
                adapter_id="paper",
                mode="PAPER",
                status="READY",
                eligibility="PAPER",
                is_active=True,
            )
        )


def _seed_demo_ready(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add(
            Account(
                account_id=DEMO_ACCOUNT_ID,
                adapter_id="ccxt",
                mode="DEMO",
                endpoint="binance_spot_testnet",
                status="READY",
                eligibility="DEMO_CERTIFIED",
                is_active=False,
            )
        )


def _seed_valid_cert(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add(
            CertificationRecord(
                cert_id="cert-valid",
                tuple_key=D1B_ALLOWLIST.canonical_key,
                valid=True,
                lifecycle_count=50,
                soak_passed=True,
            )
        )


@pytest.mark.d1c
def test_main_window_renders_broker_hub_page_when_controller_present(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.tray import TrayController
    from autotrade.app_ui.views.broker_hub_page import BrokerHubPage
    from autotrade.app_ui.views.main_window import MainWindow, PlaceholderPage

    tray = TrayController(migrated_uow)
    window = MainWindow(tray)
    try:
        assert window.show_screen("broker_hub") is True
        assert isinstance(window.pages.currentWidget(), BrokerHubPage)
        # Dashboard has no Qt view wired up yet (only its read model, T013)
        # -- it stays an untouched placeholder. kill_switch/live_monitor
        # graduated in T040/T041 -- see test_kill_switch_ui.py /
        # test_live_monitor_ui.py for their dedicated coverage.
        assert isinstance(window.pages.widget(0), PlaceholderPage)
        assert window.pages.widget(0).spec.key == "dashboard"
    finally:
        window.deleteLater()


@pytest.mark.d1c
def test_main_window_falls_back_to_placeholder_without_a_controller(qapp) -> None:  # noqa: ANN001
    from autotrade.app_ui.views.main_window import MainWindow, PlaceholderPage

    window = MainWindow()
    try:
        assert window.show_screen("broker_hub") is True
        assert isinstance(window.pages.currentWidget(), PlaceholderPage)
    finally:
        window.deleteLater()


@pytest.mark.d1c
def test_enable_demo_refused_shows_modal_and_never_flips_the_account(
    qapp, migrated_uow: UnitOfWork, warnings: list[tuple[str, str]]  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.broker_hub import BrokerHubController
    from autotrade.app_ui.views.broker_hub_page import BrokerHubPage

    page = BrokerHubPage(BrokerHubController(migrated_uow))
    try:
        assert page.enable_demo_button.isEnabled() is False  # cert invalid -> greyed
        assert "not" in page.enable_demo_button.toolTip().lower()

        page._on_enable_demo()  # simulates the button click

        assert len(warnings) == 1
        title, text = warnings[0]
        assert "refused" in title.lower()
        assert "certif" in text.lower()
        with migrated_uow.session() as session:
            assert session.get(Account, DEMO_ACCOUNT_ID) is None
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_enable_demo_allowed_flips_the_account_without_a_modal(
    qapp, migrated_uow: UnitOfWork, warnings: list[tuple[str, str]], fake_keyring: FakeKeyring  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.broker_hub import BrokerHubController
    from autotrade.app_ui.views.broker_hub_page import BrokerHubPage

    _seed_valid_cert(migrated_uow)
    # G1.2/G7 precondition: Enable DEMO now also needs credentials stored (or
    # an already-provisioned DEMO account) — neither exists yet here, so seed
    # the credentials the same way the Owner's "Save credentials" form would.
    _seed_demo_credentials(fake_keyring)
    page = BrokerHubPage(BrokerHubController(migrated_uow))
    try:
        assert page.enable_demo_button.isEnabled() is True

        page._on_enable_demo()

        assert warnings == []
        with migrated_uow.session() as session:
            acc = session.get(Account, DEMO_ACCOUNT_ID)
            assert acc is not None
            assert acc.is_active is True
        assert "VALID" in page.cert_status.text()
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_switch_rejected_open_recon_shows_the_exact_reason_code_in_a_modal(
    qapp, migrated_uow: UnitOfWork, warnings: list[tuple[str, str]]  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.broker_hub import BrokerHubController
    from autotrade.app_ui.views.broker_hub_page import BrokerHubPage

    _seed_paper_active(migrated_uow)
    _seed_demo_ready(migrated_uow)
    with migrated_uow.session() as session:
        session.add(
            ReconBreak(
                type="orphan",
                payload={"account_id": DEFAULT_PAPER_ACCOUNT_ID},
                status="open",
                at=datetime.now(UTC),
            )
        )
    page = BrokerHubPage(BrokerHubController(migrated_uow))
    try:
        page._on_switch_demo()  # drives through the exact button handler path

        assert len(warnings) == 1
        title, text = warnings[0]
        assert "refused" in title.lower()
        assert "open_recon" in text
        with migrated_uow.session() as session:
            # Refused switch must never leave the target flipped active.
            assert session.get(Account, DEMO_ACCOUNT_ID).is_active is False
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_switch_to_demo_refused_when_not_provisioned_shows_modal(
    qapp, migrated_uow: UnitOfWork, warnings: list[tuple[str, str]]  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.broker_hub import BrokerHubController
    from autotrade.app_ui.views.broker_hub_page import BrokerHubPage

    _seed_paper_active(migrated_uow)
    page = BrokerHubPage(BrokerHubController(migrated_uow))
    try:
        page._on_switch_demo()

        assert len(warnings) == 1
        _, text = warnings[0]
        assert "no DEMO account" in text
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_switch_to_demo_succeeds_without_a_modal(
    qapp, migrated_uow: UnitOfWork, warnings: list[tuple[str, str]]  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.broker_hub import BrokerHubController
    from autotrade.app_ui.views.broker_hub_page import BrokerHubPage

    _seed_paper_active(migrated_uow)
    _seed_demo_ready(migrated_uow)
    page = BrokerHubPage(BrokerHubController(migrated_uow))
    try:
        page._on_switch_demo()

        assert warnings == []
        with migrated_uow.session() as session:
            assert session.get(Account, DEMO_ACCOUNT_ID).is_active is True
    finally:
        page.deleteLater()


# --- credential form (G1.2/G7 "tự kết nối") -------------------------------


@pytest.mark.d1c
def test_credential_form_fields_are_password_echo_mode(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from PySide6.QtWidgets import QLineEdit

    from autotrade.app_ui.controllers.broker_hub import BrokerHubController
    from autotrade.app_ui.views.broker_hub_page import BrokerHubPage

    page = BrokerHubPage(BrokerHubController(migrated_uow))
    try:
        assert page.demo_api_key_input.echoMode() == QLineEdit.EchoMode.Password
        assert page.demo_api_secret_input.echoMode() == QLineEdit.EchoMode.Password
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_credential_form_clears_fields_after_a_successful_save(
    qapp, migrated_uow: UnitOfWork, warnings: list[tuple[str, str]]  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.broker_hub import BrokerHubController
    from autotrade.app_ui.views.broker_hub_page import BrokerHubPage

    page = BrokerHubPage(BrokerHubController(migrated_uow))
    try:
        page.demo_api_key_input.setText("a-plaintext-key")
        page.demo_api_secret_input.setText("a-plaintext-secret")

        page._on_save_demo_credentials()

        assert warnings == []
        assert page.demo_api_key_input.text() == ""
        assert page.demo_api_secret_input.text() == ""
        assert "saved" in page.demo_credentials_result_label.text().lower()
        assert "configured" in page.demo_credentials_status_label.text().lower()
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_credential_form_clears_fields_after_a_failed_save(
    qapp, migrated_uow: UnitOfWork, warnings: list[tuple[str, str]]  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.broker_hub import BrokerHubController
    from autotrade.app_ui.views.broker_hub_page import BrokerHubPage

    page = BrokerHubPage(BrokerHubController(migrated_uow))
    try:
        page.demo_api_key_input.setText("a-plaintext-key")
        page.demo_api_secret_input.setText("")  # missing secret -> refused

        page._on_save_demo_credentials()

        assert len(warnings) == 1
        assert page.demo_api_key_input.text() == ""
        assert page.demo_api_secret_input.text() == ""
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_no_widget_ever_displays_a_previously_stored_credential_value(
    qapp, migrated_uow: UnitOfWork, fake_keyring: FakeKeyring  # noqa: ANN001
) -> None:
    from PySide6.QtWidgets import QLabel, QLineEdit

    from autotrade.app_ui.controllers.broker_hub import BrokerHubController
    from autotrade.app_ui.views.broker_hub_page import BrokerHubPage

    _seed_demo_credentials(fake_keyring)
    page = BrokerHubPage(BrokerHubController(migrated_uow))
    try:
        widgets: list[QLabel | QLineEdit] = [
            *page.findChildren(QLabel),
            *page.findChildren(QLineEdit),
        ]
        for widget in widgets:
            text = widget.text()
            assert "seed-key" not in text
            assert "seed-secret" not in text
        assert "configured" in page.demo_credentials_status_label.text().lower()
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_test_and_enable_buttons_disabled_when_nothing_configured(
    qapp, migrated_uow: UnitOfWork  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.broker_hub import BrokerHubController
    from autotrade.app_ui.views.broker_hub_page import BrokerHubPage

    # No DEMO account, no cert, no credentials — nothing configured at all.
    page = BrokerHubPage(BrokerHubController(migrated_uow))
    try:
        assert page.test_connection_button.isEnabled() is False
        assert "credentials" in page.test_connection_button.toolTip().lower()
        assert page.enable_demo_button.isEnabled() is False
    finally:
        page.deleteLater()


@pytest.mark.d1c
def test_test_and_enable_buttons_reflect_stored_credentials(
    qapp, migrated_uow: UnitOfWork, fake_keyring: FakeKeyring  # noqa: ANN001
) -> None:
    from autotrade.app_ui.controllers.broker_hub import BrokerHubController
    from autotrade.app_ui.views.broker_hub_page import BrokerHubPage

    _seed_valid_cert(migrated_uow)
    page = BrokerHubPage(BrokerHubController(migrated_uow))
    try:
        # Cert valid but no credentials/account yet -> still store-first gated.
        assert page.test_connection_button.isEnabled() is False
        assert page.enable_demo_button.isEnabled() is False

        page.demo_api_key_input.setText("k")
        page.demo_api_secret_input.setText("s")
        page._on_save_demo_credentials()

        assert page.test_connection_button.isEnabled() is True
        assert page.enable_demo_button.isEnabled() is True
    finally:
        page.deleteLater()
