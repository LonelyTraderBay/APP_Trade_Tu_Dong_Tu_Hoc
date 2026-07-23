<!--
Sync Impact Report
- Version change: 1.0.1 → 1.1.0
- Modified principles:
  - I. Architecture Doc Is Law → absolute primacy of v1.4; Enterprise advisory-only (MUST NEVER override)
  - IV. Phase Discipline → explicit D1a → D1b (post D0-11) → D1c → D1.1 LIVE → D3 → D4; D1 ML/`ai_*` ban
  - VI. Determinism & Evidence → D1 default `rule_sma_cross_v1`; `feature_schema_version`; closed candle only
  - VII. Simplicity for One Maintainer → enumerated trading invariants (process, no localhost HTTP,
    Risk+intent before network, UNKNOWN no blind retry, broker vs SQLite truth, keyring-only secrets)
- Added sections: none (no new principle titles; content folded into I/IV/VI/VII)
- Removed sections: none
- Templates requiring updates:
  - `.specify/templates/plan-template.md` ✅ updated (Constitution Check gates)
  - `.specify/templates/spec-template.md` ✅ updated (phase/scope assumptions)
  - `.specify/templates/tasks-template.md` ✅ updated (desktop layout + D1 forbidden deps)
  - Speckit skills (`.cursor/skills/speckit-*/SKILL.md`) ✅ no outdated agent-specific refs; no edit
  - `AGENTS.md` ✅ already aligned with this amendment; no edit
- Follow-up TODOs: none
-->

# AutoTrade AI Desktop Solo — Constitution

## Core Principles

### I. Architecture Doc Is Law

`Kien-truc-App-Desktop-Solo-v1.4.md` is the **absolute** normative source of truth.
Companion docs (`AGENTS.md`, this constitution, `docs/mvp-capability-matrix.md`) MUST NOT
contradict it. Enterprise blueprints (if present) are **advisory only** and MUST NEVER
override v1.4.

### II. Solo Desktop, No Cloud Identity

One Owner, Windows desktop, no app login/SaaS/multi-tenant. PIN is a safety interlock
against mistakes, not a security boundary against a compromised Windows account. Secrets
live in OS keyring only.

### III. Safety Before Alpha

Fail-closed on risk, freshness, recovery, and protection. Capital safety (Risk,
kill-switch, durable OMS, broker-side stops on LIVE) outranks feature velocity or model
sophistication. Operational soak proves operations, not profitability.

### IV. Phase Discipline (NON-NEGOTIABLE)

Ship strictly in this order (v1.4 / `AGENTS.md`):

1. **D1a** — Domain, SQLite (ADR-D03.1), Paper, Risk, OMS, Recovery, Telegram
2. **D1b** — One CCXT DEMO allowlist — only after mục 16 locks exchange/symbol (**D0-11**)
3. **D1c** — PySide6 MVP + installer
4. **D1.1** — LIVE enablement as a **separate Owner gate** (never implied by D0 or D1 soak)
5. **D3** — Deterministic Backtest/replay (freeze feature/label specs before AI)
6. **D4** — AI Module + Learning Store + sidecar (no auto-promote LIVE; AI MUST NOT call OMS)

D0 signature unlocks **D1a only**. D1a MUST use Paper + internal symbols; MUST NOT
implement CCXT trading until D0-11. D1 MUST NOT install scikit-learn, sqlite-vec, FAISS,
or create `ai_*` schema. **Backtest (D3) before AI (D4).**

### V. Adapter & AI Ports Over Hard-Coding

Broker access goes through the Broker Adapter Interface + manifest + contract tests.
AI (D4) goes through the AI Module Interface the same way. Strategy, Risk, and OMS MUST
NOT embed exchange-specific or ML-library-specific calls.

### VI. Determinism & Evidence

Decimal (or minor units) for money. Strategy signals MUST use **closed candles only**.
D1 default strategy MUST be `rule_sma_cross_v1` (v1.4 §07.3) unless mục 16 records a
different rule_id. Every feature path MUST carry `feature_schema_version`; bump on
formula change. Same inputs + seed → same Paper/Backtest results. No gate passes without
recorded evidence (versions, config, reports). Fault matrix scenarios (v1.4 §18) are
acceptance tests, not optional polish.

### VII. Simplicity for One Maintainer

One pinned CPython minor per release. Prefer boring, testable designs. Complexity
requires an ADR update in v1.4.

Non-negotiable MVP trading invariants (v1.4):

- Exactly **one trading process**; **no localhost HTTP API**
- Every exposure increase: Risk reservation + durable intent **commit before** network
- After send, `UNKNOWN`/timeout → query/reconcile; **MUST NOT** blind-retry
- Broker = current exposure truth; SQLite = intent/FSM/audit/outbox
- Secrets only via OS `keyring`; redact in log/UI/DB

## Security & Data

- Redact secrets from DB, logs, UI, crash reports, and tests.
- Telegram: private chat + Owner user ID only; D1 remote commands limited to `/status`,
  `/pnl`, `/pause`.
- Audit events are immutable; JSONL is diagnostic only.
- Single DB writer; AI sidecar (D4) MUST NOT race the trading writer.

## Development Workflow

1. Owner completes D0 (architecture §15–§20) before feature code.
2. Implement only the active phase; update capability matrix evidence at exit.
3. Contract + fault tests required for adapters; AI contract tests required before DEMO
   shadow.
4. Constitution and `AGENTS.md` amendments require the same care as architecture changes
   (document why, migration if needed).

## Governance

- All substantive PRs MUST comply with this constitution and v1.4.
- Conflicts: **v1.4 wins**; then amend constitution/`AGENTS.md` to match.
- LIVE enablement always needs a separate Owner gate (architecture §06), never implied
  by D0 or D1 soak days.
- Amendments: bump `CONSTITUTION_VERSION` (MAJOR = remove/redefine principles;
  MINOR = new/expanded guidance; PATCH = wording only); set `LAST_AMENDED_DATE` to the
  amendment day (ISO YYYY-MM-DD); keep `RATIFICATION_DATE` as original adoption.
- Compliance: Speckit plan Constitution Check and capability-matrix exit evidence MUST
  reflect these principles before a phase gate is claimed.

**Version**: 1.1.0 | **Ratified**: 2026-07-23 | **Last Amended**: 2026-07-23

Amendment 1.1.0: Sync phase ladder and trading invariants with v1.4/`AGENTS.md` without
adding new principle titles.
Amendment 1.0.1: D0 may defer exchange/symbol to pre-D1b (D0-11); D1a Paper remains the
only code gate unlocked by D0 signature.
