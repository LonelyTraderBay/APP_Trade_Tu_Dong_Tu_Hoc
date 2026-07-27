"""T052 — SettingsController: PIN, Telegram, backup, autostart. Qt-free.

Keyring is mocked (`monkeypatch` on the `keyring` module functions
`persistence.secrets` calls) so this suite never touches the real OS
credential store — same "no existing precedent, so fake it" reasoning as
`test_autostart.py` for `winreg`. `winreg` itself is mocked the same way as
`test_autostart.py` for the same reason.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from autotrade.app_ui.controllers.settings import SettingsController
from autotrade.app_ui.services import autostart as autostart_service
from autotrade.persistence.models import PinVerifier
from autotrade.persistence.uow import UnitOfWork

from .test_autostart import FakeWinreg


class FakeKeyring:
    """In-memory stand-in for the `keyring` module surface `secrets.py` uses."""

    class errors:  # noqa: N801 - mirrors keyring.errors.PasswordDeleteError shape
        class PasswordDeleteError(Exception):
            pass

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        try:
            del self._store[(service, username)]
        except KeyError as exc:
            raise self.errors.PasswordDeleteError from exc


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


# --- PIN -----------------------------------------------------------------


@pytest.mark.d1c
def test_set_pin_with_no_existing_row_allows_direct_set(migrated_uow: UnitOfWork) -> None:
    controller = SettingsController(migrated_uow)

    result = controller.set_pin(current_pin="", new_pin="1234", confirm_pin="1234")

    assert result.ok is True
    assert result.error is None
    with migrated_uow.session() as session:
        row = session.query(PinVerifier).first()
        assert row is not None
        assert row.hash != "1234"  # never the plaintext


@pytest.mark.d1c
def test_set_pin_rejects_mismatched_confirmation(migrated_uow: UnitOfWork) -> None:
    controller = SettingsController(migrated_uow)

    result = controller.set_pin(current_pin="", new_pin="1234", confirm_pin="9999")

    assert result.ok is False
    assert "match" in (result.error or "").lower()
    with migrated_uow.session() as session:
        assert session.query(PinVerifier).first() is None


@pytest.mark.d1c
def test_set_pin_change_requires_correct_current_pin(migrated_uow: UnitOfWork) -> None:
    controller = SettingsController(migrated_uow)
    controller.set_pin(current_pin="", new_pin="1234", confirm_pin="1234")

    wrong = controller.set_pin(current_pin="0000", new_pin="5678", confirm_pin="5678")
    assert wrong.ok is False
    assert "incorrect" in (wrong.error or "").lower()

    right = controller.set_pin(current_pin="1234", new_pin="5678", confirm_pin="5678")
    assert right.ok is True


@pytest.mark.d1c
def test_set_pin_too_short_is_refused_without_raising(migrated_uow: UnitOfWork) -> None:
    controller = SettingsController(migrated_uow)

    result = controller.set_pin(current_pin="", new_pin="12", confirm_pin="12")

    assert result.ok is False
    assert result.error is not None
    with migrated_uow.session() as session:
        assert session.query(PinVerifier).first() is None


# --- Telegram --------------------------------------------------------------


@pytest.mark.d1c
def test_telegram_not_configured_before_store(
    migrated_uow: UnitOfWork, fake_keyring: FakeKeyring
) -> None:
    controller = SettingsController(migrated_uow)
    assert controller.telegram_configured() is False


@pytest.mark.d1c
def test_store_telegram_persists_only_a_keyring_ref(
    migrated_uow: UnitOfWork, fake_keyring: FakeKeyring
) -> None:
    controller = SettingsController(migrated_uow)

    result = controller.store_telegram(bot_token="secret-token-abc", chat_id="12345")

    assert result.ok is True
    assert controller.telegram_configured() is True
    # The raw token must live only in the fake keyring store, never in SQLite.
    assert ("AutoTradeAI", "telegram:bot_token") in fake_keyring._store
    with migrated_uow.session() as session:
        from autotrade.persistence.models import AccountSecretsRef

        assert session.query(AccountSecretsRef).count() == 0


@pytest.mark.d1c
def test_store_telegram_requires_both_fields(
    migrated_uow: UnitOfWork, fake_keyring: FakeKeyring
) -> None:
    controller = SettingsController(migrated_uow)

    result = controller.store_telegram(bot_token="", chat_id="12345")

    assert result.ok is False
    assert controller.telegram_configured() is False


@pytest.mark.d1c
def test_clear_telegram_removes_the_keyring_refs(
    migrated_uow: UnitOfWork, fake_keyring: FakeKeyring
) -> None:
    controller = SettingsController(migrated_uow)
    controller.store_telegram(bot_token="secret-token-abc", chat_id="12345")

    controller.clear_telegram()

    assert controller.telegram_configured() is False


@pytest.mark.d1c
def test_clear_telegram_when_nothing_stored_does_not_raise(
    migrated_uow: UnitOfWork, fake_keyring: FakeKeyring
) -> None:
    controller = SettingsController(migrated_uow)

    controller.clear_telegram()  # must not raise


@pytest.mark.d1c
def test_send_test_telegram_uses_the_fake_sender_and_never_needs_a_stored_token(
    migrated_uow: UnitOfWork,
) -> None:
    controller = SettingsController(migrated_uow)

    result = controller.send_test_telegram()

    assert result.ok is True
    assert "fake sender" in result.message.lower()


# --- Backup ----------------------------------------------------------------


@pytest.mark.d1c
def test_run_backup_against_an_injected_temp_db_path(
    migrated_uow: UnitOfWork, tmp_path: Path
) -> None:
    from autotrade.persistence.engine import create_sqlite_engine

    db_path = tmp_path / "inject" / "autotrade.sqlite3"
    create_sqlite_engine(db_path)  # creates a real, valid sqlite file at db_path

    controller = SettingsController(migrated_uow)
    backup_dir = tmp_path / "backups"

    result = controller.run_backup(db_path=db_path, backup_dir=backup_dir)

    assert result.ok is True
    assert result.path is not None
    assert result.path.exists()
    assert result.path.parent == backup_dir


@pytest.mark.d1c
def test_run_backup_missing_db_returns_typed_error_not_a_raise(
    migrated_uow: UnitOfWork, tmp_path: Path
) -> None:
    controller = SettingsController(migrated_uow)

    result = controller.run_backup(db_path=tmp_path / "does-not-exist.sqlite3")

    assert result.ok is False
    assert result.path is None
    assert result.error is not None


# --- Autostart (T053) --------------------------------------------------------


@pytest.mark.d1c
def test_autostart_defaults_to_disabled(migrated_uow: UnitOfWork) -> None:
    controller = SettingsController(migrated_uow)
    assert controller.is_autostart_enabled() is False


@pytest.mark.d1c
def test_set_autostart_true_persists_preference_and_writes_registry(
    migrated_uow: UnitOfWork, fake_winreg: FakeWinreg
) -> None:
    controller = SettingsController(migrated_uow)

    result = controller.set_autostart(True)

    assert result.ok is True
    assert result.enabled is True
    assert controller.is_autostart_enabled() is True
    assert autostart_service.VALUE_NAME in fake_winreg.values


@pytest.mark.d1c
def test_set_autostart_false_clears_preference_and_registry(
    migrated_uow: UnitOfWork, fake_winreg: FakeWinreg
) -> None:
    controller = SettingsController(migrated_uow)
    controller.set_autostart(True)

    result = controller.set_autostart(False)

    assert result.ok is True
    assert controller.is_autostart_enabled() is False
    assert autostart_service.VALUE_NAME not in fake_winreg.values


@pytest.mark.d1c
def test_set_autostart_registry_failure_does_not_persist_the_preference(
    migrated_uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*args: Any, **kwargs: Any) -> None:
        raise OSError("access denied")

    monkeypatch.setattr(autostart_service, "set_autostart", _boom)
    controller = SettingsController(migrated_uow)

    result = controller.set_autostart(True)

    assert result.ok is False
    assert result.error is not None
    assert controller.is_autostart_enabled() is False
