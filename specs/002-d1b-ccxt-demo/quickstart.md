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

## Dev data paths

- Runtime DB: `%LOCALAPPDATA%/AutoTradeAI/autotrade.sqlite3`
- Dev override: `data/` (gitignore)
- Apply Alembic through D1b migration (`0002_…`)

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
# After: CLI store credentials + test-connection + cert contract/fault recorded
set AUTOTRADE_D1B_REAL=1
pytest tests/evidence/test_demo_lifecycles_real.py
# or documented headless evidence harness from tasks
```

Expect: evidence log shows ≥50 **round-trip-to-flat** DONE events on Binance Spot Testnet; mock runs absent from count.

### V8 — Real testnet soak ≥72h (SC-005) — Owner attended

```text
set AUTOTRADE_D1B_REAL=1
# start soak harness; no Owner pause; sleep/resume only with clean recovery
```

Expect: wall-clock ≥72h; end recon unresolved count = 0; pause → gate fail.

### V9 — CLI + Telegram mode tag

```text
autotrade-headless … status
# Telegram /status shows mode=DEMO or PAPER
```

Expect: secrets redacted; mode matches active account.

## Evidence → matrix

When V0–V8 pass, fill `docs/mvp-capability-matrix.md` rows for G1.1/G1.3, ADR-D09, D1b phase exit (versions, tuple, report paths). Leave LIVE rows empty.

## Out of scope here

- PySide6 Broker Hub / installer (D1c)
- LIVE enablement (D1.1)
- Multi-exchange / MT5 / AI
