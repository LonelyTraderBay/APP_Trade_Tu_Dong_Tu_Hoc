# Implementation Plan: D1b CCXT DEMO Allowlist

**Branch**: `002-d1b-ccxt-demo` | **Date**: 2026-07-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-d1b-ccxt-demo/spec.md`

**Normative refs**: `Kien-truc-App-Desktop-Solo-v1.4.md` §§05, 06, 11, 13, 14, 16, 18; `AGENTS.md`; constitution v1.1.0; D1a artifacts under `specs/001-d1a-paper-core/`

## Summary

Ship **phase D1b only**: one certified CCXT DEMO path for the Owner-locked tuple  
`binance` + spot + **Binance Spot Testnet** + `BTC/USDT` + `15m`, behind the existing Broker Adapter Interface, reusing D1a Risk → durable intent → OMS → UNKNOWN/recon invariants.

Operator surface stays **headless/CLI + keyring + Telegram** (`/status` `/pnl` `/pause` with mode `DEMO`). No LIVE, no multi-exchange, no PySide6 Broker Hub (D1c).

Evidence gates (exit D1b): contract suite for the tuple, fault injection (mock OK), **≥50 completed round-trip lifecycles on real testnet**, **≥72h wall-clock soak on real testnet** with zero unresolved recon.

**Implement gate**: rebase/branch from `main` **after PR #5 (D1a) merges**; plan/tasks may land now; `/speckit-implement` MUST wait.

## Technical Context

**Language/Version**: CPython **3.14.x** (`>=3.14,<3.15`) — inherit D1a pin; do not widen range in D1b.

**Primary Dependencies** (D1b delta on D1a allowlist):
- Existing: SQLAlchemy 2.x, Alembic, `keyring`, `python-telegram-bot`, argon2-cffi, pytest, ruff
- **Add**: `ccxt` (pin closed major/minor compatible with 3.14; hashed lockfile) — DEMO/testnet trading only
- **Forbidden still**: FastAPI, Electron, scikit-learn, sqlite-vec, FAISS, MetaTrader5, full PySide6 UI/installer (D1c), second CCXT exchange, LIVE enablement

**Storage**: Same SQLite WAL + ADR-D03.1; additive migration for certification/allowlist/active-account metadata (see [data-model.md](./data-model.md)). Runtime `%LOCALAPPDATA%/AutoTradeAI/`; secrets only in OS keyring.

**Testing**: pytest — `tests/unit|contract|integration|fault` + markers `d1a` (regression) and `d1b` (DEMO). Real-network suites gated by explicit env (e.g. `AUTOTRADE_D1B_REAL=1`) and Owner testnet keys in keyring — never CI-default. Evidence pack path for matrix G1 / ADR-D09 / E2E DEMO.

**Target Platform**: Windows 11 x64 (Owner baseline), attended-only

**Project Type**: Single-process desktop trading core — headless CLI extended for DEMO; GUI still D1c

**Performance Goals**: Correctness and fail-closed safety over throughput; OMS serialized per active account; monotonic timeouts; no duplicate exposure under fault matrix

**Constraints**:
- One trading process; **no localhost HTTP API**
- Exactly **one active account** (Paper XOR DEMO); switch only when flat + no open recon
- Allowlist tuple immutable without re-certification; refuse LIVE / other exchanges / other symbols
- Pre-SUBMITTING: Risk reservation + durable intent commit **before** any CCXT network send
- UNKNOWN → query/recon only; never blind retry / never new client_order_id for same intent
- Broker (testnet) = current exposure SoT; SQLite = intent/FSM/audit/outbox
- Strategy/Risk/OMS MUST NOT import `ccxt`; only adapter package may
- ≥50 + soak = **real** Binance Spot Testnet only; mock/fault ≠ lifecycle count
- D0-06 ToS: Owner gate before real-network credential use (not code)

**Scale/Scope**: One Owner, one certified DEMO venue/symbol/TF, one strategy `rule_sma_cross_v1`, Paper retained for switch/regression — D1b only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Derived from `.specify/memory/constitution.md` (v1.1.0+) and
`Kien-truc-App-Desktop-Solo-v1.4.md` (absolute source of truth; Enterprise advisory only):

- [x] Plan scope maps to **one** active phase: **D1b only** (D1c / D1.1 LIVE / D3 / D4 later)
- [x] D0-11 locked (`binance`/spot/Binance Spot Testnet/`BTC/USDT`/`15m`); CCXT DEMO trading allowed in this phase only for that tuple; still excludes scikit-learn / sqlite-vec / FAISS / `ai_*`
- [x] Invariants preserved: one trading process; no localhost HTTP API; Risk reservation +
      durable intent commit before network; `UNKNOWN` → query/recon (no blind retry);
      broker = exposure truth; SQLite = intent/FSM/audit/outbox; secrets via keyring only
- [x] D1 strategy default `rule_sma_cross_v1`; features carry `feature_schema_version`;
      signals use closed candles only (`BTC/USDT` `15m` on DEMO)
- [x] Adapter access via ports + contract tests; no exchange SDK hard-coding in
      Strategy/Risk/OMS; AI (D4) not in scope; AI MUST NOT call OMS
- [x] Evidence plan named (unit → contract → fault §18 → real DEMO lifecycle ≥50 + soak ≥72h / capability matrix)

**Post-design re-check**: PASS — `research.md`, `data-model.md`, `contracts/*`, `quickstart.md` stay inside D1b, preserve D1a OMS/UNKNOWN/Risk, encode §05 certification + allowlist, and defer UI/LIVE/AI.

## Project Structure

### Documentation (this feature)

```text
specs/002-d1b-ccxt-demo/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   ├── allowlist-tuple.md
│   ├── ccxt-demo-adapter.md
│   ├── account-switch.md
│   ├── cli-demo-ops.md
│   └── certification-evidence.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/autotrade/
├── entrypoints/
│   └── headless.py              # extend CLI: demo credentials, test, enable, switch
├── core/
│   ├── domain/                  # unchanged invariants; maybe allowlist value objects
│   ├── adapters/
│   │   ├── protocol.py          # existing Broker Adapter Interface
│   │   ├── paper.py             # retain
│   │   ├── registry.py          # built-in registry; certify only locked tuple
│   │   └── ccxt_demo/           # NEW — binance spot testnet only
│   │       ├── adapter.py
│   │       ├── manifest.py
│   │       └── sandbox.py       # endpoint/mode guard (refuse LIVE endpoints)
│   ├── market/                  # candle ingest from DEMO adapter for BTC/USDT 15m
│   ├── features/                # same schema versioning; closed candles only
│   ├── strategy/                # rule_sma_cross_v1 — no ccxt imports
│   ├── risk/                    # unchanged semantics
│   ├── oms/                     # unchanged submit/UNKNOWN/recovery protocol
│   ├── ledger/                  # recon against DEMO broker truth
│   ├── certify/                 # NEW — certification record + invalidation rules
│   ├── accounts/                # NEW or extend — single active account switch
│   └── notify/                  # Telegram mode tag DEMO|PAPER
└── persistence/                 # Alembic 0002+ for certify/allowlist/active flags

tests/
├── unit/                        # allowlist, sandbox guard, switch rules
├── contract/                    # ccxt_demo port + allowlist negatives
├── integration/                 # Paper regression + DEMO path (mock network default)
├── fault/                       # §18 inject on DEMO adapter double
└── evidence/                    # optional harnesses for real lifecycle/soak (manual/gated)

data/                            # dev only, gitignore
```

**Structure Decision**: Extend v1.4 §13 layout. Add `adapters/ccxt_demo/` + thin `certify/` + account-active helper. Do **not** create `app_ui/`, `core/ai/`, `backtest/`, `plugins/`, or `api/`. Do not scaffold a generic multi-exchange CCXT factory for trading — only the locked tuple may reach `place_order`.

## Design highlights (mandatory)

### Allowlist + certification (§05.3–05.5)

- Hard fail-closed if `exchange_id`, market, sandbox endpoint class, symbol, or TF ≠ locked tuple.
- Certification record required before DEMO trading READY; invalidation on library/endpoint/credential-scope/instrument metadata change (FR-009).
- LIVE mode remains hard-disabled; separate credential records never promoted DEMO→LIVE in-place (§06).

### CCXT DEMO adapter

- Implements the **same** Broker Adapter Interface as Paper (`place`, `cancel`, `query_by_client_id`, open orders, executions cursor+overlap, positions, balances, protection best-effort per capability snapshot).
- Pins sandbox/testnet configuration for Binance Spot Testnet; refuse production REST hosts for trading.
- Strategy/Risk/OMS see only domain types; import-linter (or equivalent) forbids `ccxt` outside `adapters/ccxt_demo`.

### Account switch (Paper ↔ DEMO)

- Exactly one `accounts.is_active` (or equivalent) at a time.
- Switch CLI refuses unless flat + no open recon + no UNKNOWN intents.
- Telegram `/status`/`/pnl`/`/pause` always include active `mode`.

### CLI surface (no D1c UI)

Commands (names finalized in tasks; contract in `contracts/cli-demo-ops.md`):
- store DEMO key/secret refs in keyring
- `test-connection` / capability probe
- `enable-demo` / `disable-demo` (requires valid certification for enable)
- `switch-account paper|demo`

### Evidence exit

| Gate | How | Counts to ≥50 / soak? |
|---|---|---|
| Contract suite | pytest `tests/contract` (+ mock CCXT) | No |
| Fault §18 inject | pytest `tests/fault` on adapter double | No |
| ≥50 round-trips | real testnet harness + evidence log | Yes |
| ≥72h soak | real testnet wall-clock, no Owner pause | Yes |
| D1a regression | `pytest -m d1a` | N/A (must pass) |

### Blocking prerequisites (not code tasks)

1. Merge PR #5 → rebase `002-d1b-ccxt-demo` onto `main`.
2. Owner completes D0-06 ToS for Binance Spot Testnet / bot use before real keys.
3. Owner provisions testnet API key (trade-only, no withdraw) into keyring via CLI — never commit secrets.

## Later phases (not planned here)

- **D1c**: PySide6 Broker Hub / Settings / installer
- **D1.1**: LIVE certification gate (separate)
- **D2 / D3 / D4**: second adapter, Backtest, AI

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
