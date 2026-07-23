# Contract: UI → Core command boundary

**Phase**: D1c  
**Invariant**: UI never imports `ccxt`, never writes trading tables directly, never enables LIVE.

## Allowed commands (illustrative)

| Command | PIN? | Notes |
|---|---|---|
| `get_dashboard_snapshot` | No | Read-only |
| `test_demo_connection` | No | Uses keyring; redacted caps |
| `enable_demo` / `disable_demo` | PIN if policy says so; cert valid required | Same as headless |
| `switch_account(paper\|demo)` | No | Fail-closed flat/recon/UNKNOWN |
| `pause_l1` / tray Pause | **No PIN** | Always available |
| `flatten_local` | **No PIN** | Confirm dialog only |
| `resume_or_raise_risk` | **PIN** | |
| `save_telegram_settings` | PIN | keyring only |
| `export_history_csv` | No | Redacted fields |

## Errors

- Cert invalid → `CertificationNotValid` surfaced as modal, no partial enable.
- Switch rejected → show reason codes (`not_flat`, `open_recon`, `unknown_or_submitting`).
