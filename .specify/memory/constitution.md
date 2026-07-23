# AutoTrade AI Desktop Solo — Constitution

## Core Principles

### I. Architecture Doc Is Law

`Kien-truc-App-Desktop-Solo-v1.4.md` is the normative source of truth. Companion docs (`AGENTS.md`, this constitution, `docs/mvp-capability-matrix.md`) must not contradict it. Enterprise blueprints are advisory only.

### II. Solo Desktop, No Cloud Identity

One Owner, Windows desktop, no app login/SaaS/multi-tenant. PIN is a safety interlock against mistakes, not a security boundary against a compromised Windows account. Secrets live in OS keyring only.

### III. Safety Before Alpha

Fail-closed on risk, freshness, recovery, and protection. Capital safety (Risk, kill-switch, durable OMS, broker-side stops on LIVE) outranks feature velocity or model sophistication. Operational soak proves operations, not profitability.

### IV. Phase Discipline (NON-NEGOTIABLE)

Ship in order: **D1 trading path → D3 Backtest → D4 AI**. Do not install ML/vector dependencies or `ai_*` schema in D1. Do not auto-promote models to LIVE. Backtest must freeze feature/label specs before AI training.

### V. Adapter & AI Ports Over Hard-Coding

Broker access goes through the Broker Adapter Interface + manifest + contract tests. AI (D4) goes through the AI Module Interface the same way. Strategy, Risk, and OMS must not embed exchange-specific or ML-library-specific calls.

### VI. Determinism & Evidence

Decimal (or minor units) for money. Closed-candle signals only. Same inputs + seed → same Paper/Backtest results. No gate passes without recorded evidence (versions, config, reports). Fault matrix scenarios are acceptance tests, not optional polish.

### VII. Simplicity for One Maintainer

One pinned CPython minor per release, one trading process, SQLite, no Kafka/K8s/local HTTP API in MVP. Prefer boring, testable designs. Complexity requires an ADR update in the architecture doc.

## Security & Data

- Redact secrets from DB, logs, UI, crash reports, and tests.
- Telegram: private chat + Owner user ID only; D1 remote commands limited to `/status`, `/pnl`, `/pause`.
- Audit events are immutable; JSONL is diagnostic only.
- Single DB writer; AI sidecar (D4) must not race the trading writer.

## Development Workflow

1. Owner completes D0 (architecture §15–§20) before feature code.
2. Implement only the active phase; update capability matrix evidence at exit.
3. Contract + fault tests required for adapters; AI contract tests required before DEMO shadow.
4. Constitution and `AGENTS.md` amendments require the same care as architecture changes (document why, migration if needed).

## Governance

- All substantive PRs must comply with this constitution and v1.4.
- Conflicts: **v1.4 wins**; then amend constitution/`AGENTS.md` to match.
- LIVE enablement always needs a separate Owner gate (architecture §06), never implied by D0 or D1 soak days.

**Version**: 1.0.1 | **Ratified**: 2026-07-23 | **Last Amended**: 2026-07-23

Amendment 1.0.1: D0 may defer exchange/symbol to pre-D1b (D0-11); D1a Paper remains the only code gate unlocked by D0 signature.
