# Data Model: D1c Desktop MVP

**Normative**: Không đổi ADR-D03.1 trading schema. UI đọc/ghi qua core commands — **không** SQL trực tiếp từ Qt.  
**Baseline**: D1a + D1b tables. **No `ai_*`.**

## Entity overview (UI-facing projections)

```text
ActiveAccountView
  account_id, mode (PAPER|DEMO), endpoint_class, cert_valid, is_ready

DashboardSnapshot
  equity, pnl_day, ks_level, recovery_status, outbox_backlog, adapter_connected, data_age_sec

BrokerHubState
  paper_account?, demo_account?, capabilities_redacted?, last_test_at?, last_error_redacted?

LiveMonitorRow
  intent_id, client_order_id, state, delivery_certainty, symbol, side, qty, updated_at

HistoryQuery
  filters: type, correlation_id, client_order_id, time_range → CSV export

UiSettings (non-secret)
  currency_display, autostart, theme?, last_window_geometry
  secrets remain keyring refs only (PIN hash, Telegram token ref)
```

## Persistence delta (optional, additive only)

| Table / store | Purpose | Rules |
|---|---|---|
| `ui_settings` **NEW** (optional) | Window geometry, autostart flag, non-secret prefs | No secrets; JSON OK |
| Existing `pin_verifier` | Unlock Settings / resume | Unchanged D1a |
| Existing `account_secrets_ref` | Telegram/DEMO keys | UI chỉ store via keyring helpers |
| Existing `certification_records` | Gate Enable DEMO | UI must call `assert_cert_valid_for_trading` |

**Không** tạo bảng trading mới cho UI. Prefer read models over denormalized UI tables.

## Command boundary

```text
Qt View → UiController → core.* (accounts / certify / oms / risk / notify)
                         ↘ UnitOfWork / Runtime queue (ADR-D13)
```

Forbidden: `from PySide6` inside `core/`, `persistence/`, `strategy/`, `risk/`, `oms/`.

## Single-instance & tray

- OS mutex / QLocalServer name `AutoTradeAI.Solo` (exact string in tasks).
- `autotrade-headless` (T015) acquires the same shared lock, not a second one — desktop and headless mutually exclude each other, enforcing v1.4 "one trading process" across both entrypoints.
- Tray holds Pause → `KillSwitch.pause_l1` without PIN.

## Packaging artifacts (not DB)

- `%LOCALAPPDATA%/AutoTradeAI/` data
- Install dir one-folder PyInstaller
- Backup = copy SQLite + settings (exclude nothing secret from keyring — keyring stays OS)
