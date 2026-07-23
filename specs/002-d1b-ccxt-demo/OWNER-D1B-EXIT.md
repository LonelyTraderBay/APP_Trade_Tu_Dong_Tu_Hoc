# Owner checklist — D1b architecture exit (attended)

Harness/CLI is ready on branch `002-d1b-ccxt-demo`. This file is the **Owner-only** wall-clock path; agents must not mark cert.valid by backdating soak.

## Before REAL

- [x] D0-06: review Binance Spot Testnet / bot ToS (Owner 2026-07-23)
- [x] Create testnet API key (trade enabled, **withdraw disabled**) — stored in OS keyring
- [x] `autotrade-headless demo-store-creds --account-id demo-binance` (secrets stay in OS keyring)
- [x] `set AUTOTRADE_D1B_REAL=1`
- [x] `autotrade-headless demo-test-connection` → caps redacted OK
- [x] `pytest -m "d1a or d1b"` green (mocks)
- [x] `autotrade-headless cert-mark-contract` then `cert-mark-fault` (sau Alembic upgrade runtime DB)

## V7 — ≥50 round-trips

- [x] Smoke: `autotrade-headless run-lifecycles --count 2`
- [x] Full: `autotrade-headless run-lifecycles --count 50`
- [x] `autotrade-headless cert-status` → `lifecycle_count >= 50` (52 @ 2026-07-23)

## V8 — ≥72h soak

- [ ] Machine can stay up; avoid Owner pause (`soak-abort` fails the gate)
- [ ] `autotrade-headless run-soak --hours 72 --heartbeat-seconds 300` — **STARTED** 2026-07-23 `soak_cb50ba457b9d9a1b` (do not start a second soak)
- [ ] `autotrade-headless soak-status` → passed; recon unresolved = 0
- [ ] `autotrade-headless cert-status` → `soak_passed=true`, `valid=true`

## Enable + matrix

- [ ] `autotrade-headless enable-demo --account-id demo-binance`
- [ ] Fill Evidence in `docs/mvp-capability-matrix.md` (ADR-D09 + D1b exit): app version, ccxt version, dates, DB path — update soak≥72h + cert.valid when V8 ends
- [ ] Do **not** commit API keys, PIN, Chat ID, or raw dumps with secrets
- [ ] Rotate testnet API key if it was ever pasted into chat

## Runtime DB bootstrap (trước cert-mark lần đầu)

```text
# Alembic tới head trên %LOCALAPPDATA%/AutoTradeAI (hoặc AUTOTRADE_DATA_DIR)
python -c "from pathlib import Path; from alembic.config import Config; from alembic import command; c=Config('src/autotrade/persistence/alembic.ini'); c.set_main_option('script_location','src/autotrade/persistence/alembic'); command.upgrade(c,'head')"
```

## Sau khi soak passed (copy-paste)

```powershell
cd C:\Users\C-PC\Documents\APP_Trade_Tu_Dong_Tu_Hoc
.\.venv\Scripts\Activate.ps1
python -m autotrade.entrypoints.headless soak-status
python -m autotrade.entrypoints.headless cert-status
# expect: soak_passed=true, valid=true
python -m autotrade.entrypoints.headless enable-demo --account-id demo-binance
python -m autotrade.entrypoints.headless status
# rồi cập nhật docs/mvp-capability-matrix.md ADR-D09 (soak date + valid=true)
```

See also: [quickstart.md](./quickstart.md) Owner runbook.
