# Quickstart: Validate D1b CCXT DEMO Allowlist

**Feature**: `002-d1b-ccxt-demo`  
**Goal**: Prove D1b gates without LIVE/UI/AI; preserve D1a Paper invariants.

## Prerequisites

- Windows 11 x64
- CPython 3.14.x per D1a pin
- **D1a merged to `main`** (PR #5) and this branch rebased — required before implementing/running DEMO trading code
- Owner D0-06 ToS review for Binance Spot Testnet / bot use (before real keys)
- Testnet API key in OS keyring via CLI only — **never** commit secrets
- Docs: [plan.md](./plan.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Real-network gate:** set `AUTOTRADE_D1B_REAL=1` only for Owner-attended V7/V8 on Binance Spot Testnet. Default CI/dev runs use mocks; never commit API keys.

## Dev data paths

- Runtime DB: `%LOCALAPPDATA%/AutoTradeAI/autotrade.sqlite3`
- Dev override: `data/` (gitignore)
- Apply Alembic through D1b migration (`0002_…`) before first `cert-mark-*` / REAL runners on the runtime DB:

```powershell
python -c "from pathlib import Path; from alembic.config import Config; from alembic import command; c=Config('src/autotrade/persistence/alembic.ini'); c.set_main_option('script_location','src/autotrade/persistence/alembic'); command.upgrade(c,'head')"
```

## Validation scenarios

### V0 — D1a regression (SC-006)

```text
pytest -m d1a
```

Expect: all prior Paper/Risk/OMS/UNKNOWN/Telegram suites still PASS after DEMO code lands.

### V1 — Allowlist negatives (SC-001 / SC-007)

```text
pytest tests/contract/test_allowlist_tuple.py
```

Expect: non-tuple exchange/symbol/TF/LIVE/production endpoint refused before any send.

### V2 — Durable submit on DEMO path (SC-002)

```text
pytest tests/integration/test_durable_submit_demo.py
```

Expect: intent+reservation+audit committed before mocked CCXT send; commit fail → no send.

### V3 — UNKNOWN no blind retry on DEMO adapter (SC-003)

```text
pytest tests/fault/test_demo_timeout_unknown.py
```

Expect: query/recon only; zero duplicate exposure; reservation held.

### V4 — Account switch (FR-005)

```text
pytest tests/integration/test_account_switch.py
```

Expect: Paper↔DEMO OK when flat; refused when non-flat / open recon / UNKNOWN.

### V5 — Contract suite (mock) for certification step 2

```text
pytest tests/contract -m d1b
```

Expect: place/cancel/query_by_client_id/pagination/sandbox guard PASS for locked tuple.

### V6 — Fault suite (inject) for certification step 3

```text
pytest tests/fault -m d1b
```

Expect: §18-aligned DEMO faults PASS; do **not** increment lifecycle counter.

### V7 — Real testnet ≥50 lifecycles (SC-004) — Owner attended

```text
# 0) ToS + testnet key (trade-only, no withdraw) — never commit secrets
# 1) Store creds + probe
autotrade-headless demo-store-creds --account-id demo-binance
set AUTOTRADE_D1B_REAL=1
autotrade-headless demo-test-connection

# 2) Mark mock suites (after pytest contract/fault green)
autotrade-headless cert-mark-contract
autotrade-headless cert-mark-fault
autotrade-headless cert-status

# 3) Smoke 1–2 round-trips, then full ≥50
set AUTOTRADE_D1B_LIFECYCLE_COUNT=2
pytest tests/evidence/test_demo_lifecycles_real.py -m d1b
# or:
autotrade-headless run-lifecycles --count 2 --account-id demo-binance

set AUTOTRADE_D1B_LIFECYCLE_COUNT=50
autotrade-headless run-lifecycles --count 50 --account-id demo-binance
autotrade-headless cert-status
```

Expect: `lifecycle_count >= 50`; only `source=real_testnet` counted; no UNKNOWN left open; secrets redacted in logs.

### V8 — Real testnet soak ≥72h (SC-005) — Owner attended

```text
set AUTOTRADE_D1B_REAL=1
# Full continuous soak (writes soak_passed + try_promote_valid when ≥72h + unresolved=0)
autotrade-headless run-soak --hours 72 --heartbeat-seconds 300 --account-id demo-binance

# Monitor / abort (abort = Owner pause → continuous gate FAIL — do not use for exit)
autotrade-headless soak-status
# autotrade-headless soak-abort

# Short local smoke only (does NOT write cert valid):
# autotrade-headless run-soak --hours 0.01
# pytest evidence soak smoke (connect+abort) when REAL=1
```

Expect: wall-clock ≥72h; no Owner pause; sleep/resume OK only if recovery/recon clean; end `unresolved_recon=0`; then `cert-status` shows `soak_passed=true` and `valid=true` (if lifecycle≥50 + contract/fault already marked).

### V9 — enable-demo after valid cert

```text
autotrade-headless cert-status
autotrade-headless enable-demo --account-id demo-binance
autotrade-headless status
```

Expect: enable refused while `valid=false`; succeeds only after V7+V8 promote.

### V10 — CLI + Telegram mode tag

```text
autotrade-headless status
# Telegram /status shows mode=DEMO or PAPER
```

Expect: secrets redacted; mode matches active account.

## Owner runbook — D1b exit (attended)

Complete in order; **do not** fake soak duration for `valid=true`.

| Step | Action | Done when |
|---|---|---|
| R0.1 | D0-06 ToS Binance Spot Testnet / bot | Owner reviewed |
| R0.2 | Create testnet API key (trade-only, **no withdraw**) | Key in OS keyring via `demo-store-creds` |
| R0.3 | Windows machine stays available; sleep/resume OK if recovery clean | Machine ready |
| V5–V6 | `pytest -m "d1a or d1b"` (mocks) | Green; then `cert-mark-contract` / `cert-mark-fault` |
| V7 | `AUTOTRADE_D1B_REAL=1` + `run-lifecycles --count 50` | `cert-status` lifecycle_count ≥ 50 |
| V8 | `run-soak --hours 72` (no `soak-abort`) | soak_passed; `valid=true` after promote |
| V9 | `enable-demo` | status mode=DEMO |
| Matrix | Fill Evidence below with versions / paths | D1b exit row complete |

**Evidence pack paths (Owner fills after V7/V8):**

- DB: `%LOCALAPPDATA%/AutoTradeAI/autotrade.sqlite3` (`certification_records`, `lifecycle_evidence`, `soak_runs`)
- Optional log dump under `evidence/` (gitignored) — never paste API keys

## Evidence → matrix

When V0–V8 pass, fill `docs/mvp-capability-matrix.md` rows for G1.1/G1.3, ADR-D09, D1b phase exit (versions, tuple, report paths). Leave LIVE rows empty.

## Out of scope here

- PySide6 Broker Hub / installer (D1c)
- LIVE enablement (D1.1)
- Multi-exchange / MT5 / AI
