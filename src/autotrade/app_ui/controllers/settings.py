"""T052/T053 — Settings controller: PIN, Telegram, backup, autostart. Qt-free.

Contract (`contracts/ui-core-boundary.md`):
- PIN change reuses `persistence.pin.hash_pin`/`verify_pin` (Argon2id)
  verbatim — no hashing is reimplemented here. The plaintext PIN is only
  ever passed into those two functions; it is never logged, printed, or
  persisted anywhere else. If no `PinVerifier` row exists yet, a PIN can be
  set directly (no current-PIN check) — mirrors the task brief.
- Telegram credentials follow the exact keyring-ref pattern
  `headless.py`'s `_demo_store_creds` uses (`persistence.secrets.SecretRef`
  / `store_secret`): only a service+username *reference* is ever persisted;
  the bot token itself never touches SQLite and this controller never
  returns it back to the view once stored — `telegram_configured()` reports
  presence only. "Send test message" mirrors headless's `--test-telegram`
  path exactly (`FakeTelegramSender` — no real Telegram Bot API sender
  exists in this codebase yet; that gap is pre-existing and out of scope
  here).
- Backup wires the already-tested `persistence.backup.snapshot_database`
  against the real runtime DB path (`persistence.engine.default_db_path`)
  by default; tests inject `db_path` to avoid ever touching a real machine's
  data directory.
- Autostart (T053) writes the Windows Run-key via
  `app_ui.services.autostart` AND mirrors the on/off preference into the
  existing `app_settings` table — the checkbox always reflects the
  persisted preference, not a live registry re-read, so it stays consistent
  even if the registry write is later revoked outside the app.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from autotrade.app_ui.services import autostart as autostart_service
from autotrade.app_ui.services.settings import (
    SettingsView,
    build_settings_view,
    read_autostart_setting,
    write_autostart_setting,
)
from autotrade.core.domain.redaction import redact_text
from autotrade.persistence.models import PinVerifier
from autotrade.persistence.pin import PinState, hash_pin, verify_pin
from autotrade.persistence.secrets import SecretRef, delete_secret, load_secret, store_secret
from autotrade.persistence.uow import UnitOfWork

KEYRING_SERVICE = "AutoTradeAI"
TELEGRAM_TOKEN_USER = "telegram:bot_token"
TELEGRAM_CHAT_USER = "telegram:chat_id"

_TELEGRAM_TOKEN_REF = SecretRef(KEYRING_SERVICE, TELEGRAM_TOKEN_USER)
_TELEGRAM_CHAT_REF = SecretRef(KEYRING_SERVICE, TELEGRAM_CHAT_USER)


@dataclass(frozen=True, slots=True)
class PinChangeResult:
    """Outcome of a PIN set/change. Never carries the plaintext PIN."""

    ok: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TelegramStoreResult:
    ok: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TelegramTestResult:
    ok: bool
    message: str


@dataclass(frozen=True, slots=True)
class BackupResult:
    ok: bool
    path: Path | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class AutostartResult:
    ok: bool
    enabled: bool
    error: str | None = None


class SettingsController:
    """Bridges the Settings screen to pin/secrets/backup/autostart commands."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    # --- read model ------------------------------------------------------

    def snapshot(self) -> SettingsView:
        with self._uow.session() as session:
            return build_settings_view(
                session, telegram_configured=self.telegram_configured()
            )

    # --- PIN ---------------------------------------------------------------

    def set_pin(self, *, current_pin: str, new_pin: str, confirm_pin: str) -> PinChangeResult:
        """Verify `current_pin` (if a PIN already exists) then set `new_pin`.

        Never raises into the view; never logs/persists a plaintext PIN
        anywhere — only `hash_pin`'s Argon2id digest is written.
        """
        if new_pin != confirm_pin:
            return PinChangeResult(ok=False, error="New PIN and confirmation do not match.")

        with self._uow.session() as session:
            row = session.query(PinVerifier).first()

            if row is None:
                try:
                    new_state = hash_pin(new_pin)
                except ValueError as exc:
                    return PinChangeResult(ok=False, error=str(exc))
                session.add(
                    PinVerifier(
                        id=1,
                        salt=new_state.salt,
                        hash=new_state.hash,
                        failed_count=0,
                        lockout_until=None,
                    )
                )
                return PinChangeResult(ok=True)

            existing = PinState(
                salt=row.salt,
                hash=row.hash,
                failed_count=row.failed_count,
                lockout_until=row.lockout_until,
            )
            verify_result = verify_pin(existing, current_pin)
            # Persist the (possibly incremented) failed_count/lockout_until
            # regardless of outcome — same lockout bookkeeping a real PIN
            # gate would apply.
            row.failed_count = verify_result.state.failed_count
            row.lockout_until = verify_result.state.lockout_until
            if not verify_result.ok:
                # `verify_pin` returns the *same* state object, unchanged,
                # when it refuses without even checking the PIN because an
                # earlier lockout is still active — that identity is how we
                # tell "still locked out" apart from "wrong PIN this time".
                reason = (
                    "PIN locked out — try again later."
                    if verify_result.state is existing
                    else "Current PIN is incorrect."
                )
                return PinChangeResult(ok=False, error=reason)

            try:
                new_state = hash_pin(new_pin)
            except ValueError as exc:
                return PinChangeResult(ok=False, error=str(exc))
            row.salt = new_state.salt
            row.hash = new_state.hash
            row.failed_count = 0
            row.lockout_until = None
            return PinChangeResult(ok=True)

    # --- Telegram (optional) ------------------------------------------------

    def telegram_configured(self) -> bool:
        return (
            load_secret(_TELEGRAM_TOKEN_REF) is not None
            and load_secret(_TELEGRAM_CHAT_REF) is not None
        )

    def store_telegram(self, *, bot_token: str, chat_id: str) -> TelegramStoreResult:
        """Keyring-ref only — the token/chat id are never written to SQLite
        and never returned to the view once stored."""
        if not bot_token or not chat_id:
            return TelegramStoreResult(
                ok=False, error="Bot token and chat id are both required."
            )
        try:
            store_secret(_TELEGRAM_TOKEN_REF, bot_token)
            store_secret(_TELEGRAM_CHAT_REF, chat_id)
        except Exception as exc:  # noqa: BLE001 - contract: never raise into Qt
            return TelegramStoreResult(ok=False, error=redact_text(str(exc)))
        return TelegramStoreResult(ok=True)

    def clear_telegram(self) -> None:
        delete_secret(_TELEGRAM_TOKEN_REF)
        delete_secret(_TELEGRAM_CHAT_REF)

    def send_test_telegram(self) -> TelegramTestResult:
        """Mirrors `headless.py --test-telegram` exactly: `FakeTelegramSender`
        is the only sender this codebase has today — no real Telegram Bot
        API integration exists yet (pre-existing gap, out of scope here)."""
        from autotrade.core.notify.telegram_transport import (
            FakeTelegramSender,
            TelegramTransport,
        )

        transport = TelegramTransport(sender=FakeTelegramSender(), chat_id="local-dev")
        result = transport.send_test_message()
        return TelegramTestResult(
            ok=bool(result.get("ok")),
            message=(
                "Test message sent (fake sender — no real Telegram Bot API"
                " integration yet)."
            ),
        )

    # --- Backup --------------------------------------------------------

    def run_backup(
        self, *, db_path: Path | None = None, backup_dir: Path | None = None
    ) -> BackupResult:
        """Wraps `persistence.backup.snapshot_database`. Defaults to the real
        runtime DB path — tests must always pass `db_path` explicitly."""
        from autotrade.persistence.backup import snapshot_database
        from autotrade.persistence.engine import default_db_path

        src = db_path or default_db_path()
        try:
            result_path = snapshot_database(src, backup_dir)
        except Exception as exc:  # noqa: BLE001 - contract: never raise into Qt
            return BackupResult(ok=False, error=str(exc))
        return BackupResult(ok=True, path=result_path)

    # --- Autostart (T053) ------------------------------------------------

    def is_autostart_enabled(self) -> bool:
        with self._uow.session() as session:
            return read_autostart_setting(session)

    def set_autostart(self, enabled: bool) -> AutostartResult:
        """Writes the Windows Run-key, then mirrors the preference into
        `app_settings`. If the registry write fails, the preference is not
        persisted either — the checkbox must not lie about what happened."""
        try:
            autostart_service.set_autostart(enabled)
        except Exception as exc:  # noqa: BLE001 - contract: never raise into Qt
            return AutostartResult(
                ok=False, enabled=self.is_autostart_enabled(), error=str(exc)
            )
        with self._uow.session() as session:
            write_autostart_setting(session, enabled)
        return AutostartResult(ok=True, enabled=enabled)
