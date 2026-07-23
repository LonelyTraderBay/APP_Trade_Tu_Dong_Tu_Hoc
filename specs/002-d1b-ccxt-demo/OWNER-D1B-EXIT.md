# Owner checklist — D1b architecture exit (attended)

Harness/CLI is ready on branch `002-d1b-ccxt-demo`. This file is the **Owner-only** wall-clock path; agents must not mark cert.valid by backdating soak.

## Before REAL

- [ ] D0-06: review Binance Spot Testnet / bot ToS
- [ ] Create testnet API key (trade enabled, **withdraw disabled**)
- [ ] `autotrade-headless demo-store-creds --account-id demo-binance` (secrets stay in OS keyring)
- [ ] `set AUTOTRADE_D1B_REAL=1`
- [ ] `autotrade-headless demo-test-connection` → caps redacted OK
- [ ] `pytest -m "d1a or d1b"` green (mocks)
- [ ] `autotrade-headless cert-mark-contract` then `cert-mark-fault`

## V7 — ≥50 round-trips

- [ ] Smoke: `autotrade-headless run-lifecycles --count 2`
- [ ] Full: `autotrade-headless run-lifecycles --count 50`
- [ ] `autotrade-headless cert-status` → `lifecycle_count >= 50`

## V8 — ≥72h soak

- [ ] Machine can stay up; avoid Owner pause (`soak-abort` fails the gate)
- [ ] `autotrade-headless run-soak --hours 72 --heartbeat-seconds 300`
- [ ] `autotrade-headless soak-status` → passed; recon unresolved = 0
- [ ] `autotrade-headless cert-status` → `soak_passed=true`, `valid=true`

## Enable + matrix

- [ ] `autotrade-headless enable-demo --account-id demo-binance`
- [ ] Fill Evidence in `docs/mvp-capability-matrix.md` (ADR-D09 + D1b exit): app version, ccxt version, dates, DB path
- [ ] Do **not** commit API keys, PIN, Chat ID, or raw dumps with secrets

See also: [quickstart.md](./quickstart.md) Owner runbook.
