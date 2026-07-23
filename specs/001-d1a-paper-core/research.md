# Research: MVP D1a Paper Core

**Feature**: `001-d1a-paper-core` | **Date**: 2026-07-23  
**Sources**: v1.4 §§03, 10, 11, 13, 18; AGENTS.md; spec clarifications 2026-07-23

## R1 — CPython minor pin (ADR-D01)

- **Decision**: Evaluate **3.14.x** first on Windows x64 with D1a dependency set (SQLAlchemy, Alembic, keyring, python-telegram-bot, pytest, ruff). On smoke failure, pin **3.13.x** then **3.12.x**. One closed range + hashed lockfile. Record in matrix before trading merges.
- **Rationale**: ADR-D01; Owner accepted candidate in mục 16. Full D1c packaging smoke (PySide6/PyInstaller) is out of D1a-00 scope but must not force a different minor later without a release migration.
- **Alternatives considered**: Open `3.12+` range (rejected — ADR-D01); multi-minor support in one release (rejected).

## R2 — Persistence stack

- **Decision**: SQLite WAL + SQLAlchemy 2.x + Alembic; single writer; paths `%LOCALAPPDATA%/AutoTradeAI/` (runtime) and `data/` (dev).
- **Rationale**: ADR-D03 / D03.1; solo maintainability; atomic pre-SUBMITTING transactions.
- **Alternatives considered**: Postgres (rejected — local solo MVP); raw sqlite3 without ORM (rejected — migration/discipline cost for ADR-D03.1 breadth).

## R3 — Concurrency model

- **Decision**: `asyncio` event loop; **one command owner** serializes OMS mutations per account; blocking SDK/calls in a **bounded** dedicated executor; Telegram long-poll in same process with ordered commands into the owner.
- **Rationale**: v1.4 §03 async table; ADR-D13 one process; prevents concurrent duplicate submits.
- **Alternatives considered**: Multi-process trading (rejected — ADR-D13); localhost HTTP between UI and core (rejected — MVP ban); unbounded thread pool (rejected — fault controllability).

## R4 — Broker boundary

- **Decision**: Broker Adapter Interface + Paper/Fake only in D1a; Strategy/Risk/OMS never import venue SDKs; synthetic instrument id `PAPER-INTERNAL-1` (or equivalent), Owner TF config.
- **Rationale**: ADR-D09, G1.1, clarifications Q5; D0-11 still TBD.
- **Alternatives considered**: Scaffold CCXT early (rejected — AGENTS/D1a ban); hard-code BTC/USDT as venue truth (rejected — clarification A).

## R5 — Paper fill fidelity

- **Decision**: Happy path = full fill + fee/slippage; partial/late only via fault injection (or explicit size fixtures later); never infer book from OHLC.
- **Rationale**: G2.3 + clarification Q1.
- **Alternatives considered**: Always slice fills 50/50 (rejected); OHLC-derived partials (forbidden).

## R6 — Durable submit / UNKNOWN

- **Decision**: Implement §11.1 protocol literally; delivery certainty axis separate from order FSM; UNKNOWN holds reservation until recon.
- **Rationale**: G3.3, §18.3 #1–#2; clarification Q2 for txn bundle.
- **Alternatives considered**: Retry on timeout (rejected); audit after send (rejected).

## R7 — Recovery lock semantics

- **Decision**: Incomplete recovery → not READY / SAFE_LOCK as applicable; no KS auto-downgrade; no exposure increase; outbox SEV1; READY only when §11.2 step 9 satisfied.
- **Rationale**: G3.6 + clarification Q3.
- **Alternatives considered**: Force L2 on every gap (optional hardening, not required); READY with warning (rejected).

## R8 — Telegram

- **Decision**: `python-telegram-bot`; durable `notify_outbox`; `telegram_updates` unique `update_id`; TTL 60s; wrong chat/user reject+audit; transient retry; permanent 4xx dead-letter; source events retained.
- **Rationale**: ADR-D04/D10, G5, clarification Q4.
- **Alternatives considered**: Custom polling (rejected); infinite retry without dead-letter (rejected); TTL 300s (not chosen).

## R9 — Test & evidence

- **Decision**: Layout `unit|contract|integration|fault`; map each D1a matrix row to a pytest marker/report artifact under a local evidence path (gitignored or `docs/` placeholders only).
- **Rationale**: §18.1–18.3; capability matrix “no evidence = not pass”.
- **Alternatives considered**: Manual kill-process as sole recovery proof (rejected — §11.3).

## R10 — What is explicitly not researched

UI toolkit choices, CCXT exchange selection, Backtest engine, AI/vector backends — deferred to D1c / D1b / D3 / D4 respectively.
