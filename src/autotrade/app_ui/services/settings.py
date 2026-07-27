"""T052 — Settings read model + `app_settings` autostart preference, Qt-free.

Covers the non-secret parts of the Settings screen:
- Whether a PIN has been set (`pin_verifier` — never the hash/salt itself).
- The Owner-locked allowlist (`D1B_ALLOWLIST`), plain read-only fields.
- The persisted autostart preference, stored as a single row in the
  existing generic `app_settings` key/value table (`AppSetting` —
  `persistence/models`). Per `data-model.md`'s `UiSettings.autostart` and
  the task brief: this is exactly what `app_settings` is for, so no new
  `ui_settings` table is created for one boolean.

Telegram configured/not-configured and the PIN hash/verify flow live in
`app_ui/controllers/settings.py` instead — both need keyring/argon2 I/O
(and, for PIN, must never persist plaintext), which is controller-shaped
work, not a plain read model.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.persistence.models import AppSetting, PinVerifier

AUTOSTART_SETTING_KEY = "ui.autostart_enabled"


@dataclass(frozen=True, slots=True)
class AllowlistView:
    """Plain, non-editable projection of the Owner-locked D1B allowlist tuple."""

    exchange_id: str
    market: str
    endpoint_class: str
    symbol: str
    timeframe: str


@dataclass(frozen=True, slots=True)
class SettingsView:
    """Everything the Settings screen renders, in one immutable read."""

    pin_configured: bool
    telegram_configured: bool
    autostart_enabled: bool
    allowlist: AllowlistView


def build_allowlist_view() -> AllowlistView:
    return AllowlistView(
        exchange_id=D1B_ALLOWLIST.exchange_id,
        market=D1B_ALLOWLIST.market,
        endpoint_class=D1B_ALLOWLIST.endpoint_class,
        symbol=D1B_ALLOWLIST.symbol,
        timeframe=D1B_ALLOWLIST.timeframe,
    )


def is_pin_configured(session: Session) -> bool:
    return session.query(PinVerifier).first() is not None


def read_autostart_setting(session: Session) -> bool:
    row = session.get(AppSetting, AUTOSTART_SETTING_KEY)
    return row is not None and row.value == "1"


def write_autostart_setting(session: Session, enabled: bool) -> None:
    row = session.get(AppSetting, AUTOSTART_SETTING_KEY)
    if row is None:
        session.add(AppSetting(key=AUTOSTART_SETTING_KEY, value="1" if enabled else "0"))
    else:
        row.value = "1" if enabled else "0"


def build_settings_view(
    session: Session, *, telegram_configured: bool
) -> SettingsView:
    return SettingsView(
        pin_configured=is_pin_configured(session),
        telegram_configured=telegram_configured,
        autostart_enabled=read_autostart_setting(session),
        allowlist=build_allowlist_view(),
    )
