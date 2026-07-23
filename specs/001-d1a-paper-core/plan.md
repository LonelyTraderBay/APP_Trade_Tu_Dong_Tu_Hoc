# Implementation Plan: MVP D1a Paper Core

**Branch**: `001-d1a-paper-core` | **Date**: 2026-07-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-d1a-paper-core/spec.md`

**Normative refs**: `Kien-truc-App-Desktop-Solo-v1.4.md` §§03, 10, 11, 13, 18; `AGENTS.md`; constitution v1.1.0

## Summary

Build the **D1a deterministic trading core** for AutoTrade AI Desktop Solo: domain ports, SQLite WAL journal (ADR-D03.1), Fake/Paper adapter, versioned features + `rule_sma_cross_v1`, Risk/KS, crash-consistent OMS with UNKNOWN semantics, Startup Recovery before READY, and mandatory Telegram outbox — **no** CCXT trading, **no** full PySide6 UI, **no** LIVE/AI/ML.

Technical approach: one asyncio process, single OMS command owner, SQLAlchemy 2.x + Alembic, Paper adapter behind Broker Adapter Interface, pytest unit|contract|integration|fault with evidence hooks for `docs/mvp-capability-matrix.md`.

**D1a-00 first**: pin one CPython minor (candidate 3.14.x; fallback 3.13/3.12 per ADR-D01) + hashed lockfile smoke on Windows **before** trading-domain code merges.

## Technical Context

**Language/Version**: CPython **3.14.x** candidate (`>=3.14,<3.15`); if Windows x64 smoke fails → pin **3.13.x** (prefer) or **3.12.x** (ADR-D01). One closed minor + lockfile hashes. Record choice in plan notes + capability matrix **before** merging trading code.

**Primary Dependencies** (D1a allowlist):
- SQLAlchemy 2.x, Alembic, `keyring`, `python-telegram-bot`, pytest, ruff
- stdlib `asyncio`, `decimal`, `zoneinfo` as needed
- **Forbidden in D1a**: FastAPI, Electron, scikit-learn, sqlite-vec, FAISS, CCXT (trading), full PySide6 UI/installer (D1c later), MetaTrader5

**Storage**: SQLite WAL (`journal_mode=WAL`, `synchronous=FULL`, `foreign_keys=ON`, bounded `busy_timeout`); runtime `%LOCALAPPDATA%/AutoTradeAI/autotrade.sqlite3`; dev `data/` (gitignore)

**Testing**: pytest — `tests/unit|contract|integration|fault` (+ evidence reports for matrix). Packaged E2E deferred to D1c.

**Target Platform**: Windows 11 x64 (Owner baseline)

**Project Type**: Single-process desktop trading core (headless entrypoint in D1a; GUI entrypoint reserved for D1c)

**Performance Goals**: Correctness over throughput; OMS serialized per account; monotonic timeouts; no duplicate exposure under fault matrix

**Constraints**:
- One trading process; **no localhost HTTP API** (ADR-D13)
- Pre-SUBMITTING atomic commit: intents + reservations + audit (+ outbox iff event)
- UNKNOWN → query/recon; never blind retry
- Broker = current exposure truth; SQLite = intent/FSM/audit/outbox
- Secrets only via keyring; redact everywhere
- Synthetic internal instrument only (`PAPER-INTERNAL-1` class); no real venue hard-code
- Paper happy path = full fill; no OHLC liquidity inference

**Scale/Scope**: One Owner, one active Paper account, one synthetic symbol, one TF, one strategy rule — D1a only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Derived from `.specify/memory/constitution.md` (v1.1.0+) and
`Kien-truc-App-Desktop-Solo-v1.4.md` (absolute source of truth; Enterprise advisory only):

- [x] Plan scope maps to **one** active phase: **D1a only** (D1b/D1c/D1.1/D3/D4 named as “later”, not planned here)
- [x] D1 work excludes scikit-learn / sqlite-vec / FAISS / `ai_*` schema and CCXT trading
      before D0-11; D1a is Paper + internal symbols only
- [x] Invariants preserved: one trading process; no localhost HTTP API; Risk reservation +
      durable intent commit before network; `UNKNOWN` → query/recon (no blind retry);
      broker = exposure truth; SQLite = intent/FSM/audit/outbox; secrets via keyring only
- [x] D1 strategy default `rule_sma_cross_v1`; features carry `feature_schema_version`;
      signals use closed candles only
- [x] Adapter access via ports + contract tests; no exchange/ML hard-coding in
      Strategy/Risk/OMS; AI (D4) not in scope
- [x] Evidence plan named (unit/FSM → contract → fault matrix §18 / capability matrix)

**Post-design re-check**: PASS — `research.md`, `data-model.md`, `contracts/*`, `quickstart.md` stay inside D1a and encode ADR-D03.1 / §11 / §18.

## Project Structure

### Documentation (this feature)

```text
specs/001-d1a-paper-core/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   ├── broker-adapter.md
│   ├── oms-submit-protocol.md
│   └── telegram-notify.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/autotrade/
├── entrypoints/                 # headless D1a; gui reserved D1c (mutual exclusion)
├── core/
│   ├── domain/                  # Decimal models, IDs, Clock ports (UTC + monotonic)
│   ├── adapters/                # Broker Adapter Interface + Paper/Fake only in D1a
│   ├── market/
│   ├── features/                # feature_schema_version; closed candle only
│   ├── strategy/                # rule_sma_cross_v1
│   ├── risk/                    # reservation + KS L1–L4
│   ├── oms/                     # durable submit, FSM, UNKNOWN
│   ├── ledger/                  # fills, positions_local, recon
│   └── notify/                  # Telegram outbox worker (toast UI chrome → D1c)
└── persistence/                 # SQLAlchemy models + Alembic; no ai_*

tests/
├── unit/
├── contract/
├── integration/
└── fault/

data/                            # dev only, gitignore
```

**Structure Decision**: Follow v1.4 §13 exactly. Do **not** create `app_ui/`, `core/ai/`, `backtest/`, `plugins/`, or `api/` in D1a. CCXT adapter package path may exist later under `adapters/` in D1b — not scaffolded for trading in this phase.

## Design highlights (mandatory)

### Broker Adapter Interface + Paper/Fake

- Protocol/ABC in `core/adapters` with manifest fields; Paper/Fake is the only built-in implementation in D1a.
- Strategy / Risk / OMS import **domain types only** — import-linter or equivalent CI check forbids exchange SDK types in those packages.
- Happy-path Paper: full fill + configured fee/slippage; partial/late via fault injection only (spec clarification).

### Durable submit + UNKNOWN (§11.1)

1. Validate closed signal, instrument, freshness.
2. One SQLite txn: intent + client_order_id → risk-check → reservation → `RESERVED` → audit (+ outbox iff event).
3. Commit OK → `SUBMITTING` → adapter call; commit fail → no send.
4. Timeout after transmission may have started → `UNKNOWN` / `MAY_HAVE_BEEN_ACCEPTED`; hold reservation; query/recon; **no blind retry**.

### Startup Recovery (§11.2) before READY

Implement checklist steps 1–10 for Paper/Fake: RECOVERING → integrity → connect/capability → load non-terminals/cursors → paginated fetch → dedup/correlate → broker wins current exposure → effective KS max → READY only if complete/fresh/no unresolved breaks → outbox Recovery OK/SEV1. Incomplete → stay locked (spec clarification).

### Schema ADR-D03.1

All tables listed in `data-model.md` must exist before D1a exit; **no** `ai_*`.

### Test layout & exit

| Layer | Proves |
|---|---|
| unit | Decimal, FSM, KS, clock, SMA/ATR/cooldown |
| contract | Paper adapter place/query/cancel/fill/pagination/fault hooks |
| integration | Strategy→Risk→OMS→Paper→ledger→outbox |
| fault | Named §18.2 D1a rows (see tasks T8); §18.3 invariants #1–#5, #7–#8 |

**Retry split**: OMS `UNKNOWN` → query/recon only (no blind order re-place). Telegram outbox may retry **delivery** with backoff; permanent 4xx → dead-letter.

**D1a exit**: §18 suites green; scripted crash produces **zero** duplicate exposure; capability-matrix D1a Evidence cells fillable (versions, seed/config, reports). Soak ≥14d is **not** a D1a exit gate.

### D1a-00 (blocking)

1. Create project skeleton + dependency lock with hashes.
2. Smoke on clean Windows: import/runtime for allowlisted deps; ruff; pytest collect empty/smoke.
3. If 3.14.x fails → document fallback minor in this plan addendum + `docs/mvp-capability-matrix.md` ADR-D01 row **before** trading PRs merge.

## Later phases (not planned here)

- **D1b**: one CCXT DEMO after D0-11 — later
- **D1c**: PySide6 MVP + installer — later
- **D1.1 / D3 / D4**: LIVE gate / Backtest / AI — later

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
