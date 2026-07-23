# Quickstart: Validate D1a Paper Core

**Feature**: `001-d1a-paper-core`  
**Goal**: Prove D1a exit criteria locally without CCXT/UI/AI.

## Prerequisites

- Windows 11 x64
- CPython minor pinned per [plan.md](./plan.md) / ADR-D01 (try 3.14.x first)
- Repo checkout on branch `001-d1a-paper-core`
- No real bot token/Chat ID committed — use keyring + local env for Telegram tests

## D1a-00 — Runtime smoke (before trading code)

```text
1. Create venv with pinned minor
2. Install deps from hashed lockfile (SQLAlchemy, Alembic, keyring, python-telegram-bot, pytest, ruff)
3. ruff check .
4. pytest --collect-only
5. Record Python version + lockfile hash in docs/mvp-capability-matrix.md (ADR-D01 evidence)
```

If 3.14.x fails: switch to 3.13.x (or 3.12.x), update plan note + matrix, **then** continue.

## Dev data paths

- Runtime DB: `%LOCALAPPDATA%/AutoTradeAI/autotrade.sqlite3`
- Dev override: `data/` (gitignore)
- Apply Alembic migrations; confirm all ADR-D03.1 tables exist (see [data-model.md](./data-model.md))

## Validation scenarios

### V1 — Deterministic Paper replay (G2.3 / SC-001)

```text
pytest tests/integration/test_paper_replay_seed.py
```

Expect: two runs, same seed/candles → identical signals/orders/fills/balances; happy-path fills are full fills.

### V2 — Durable submit + no send on commit fail (G3.1/G3.3 / SC-002)

```text
pytest tests/integration/test_durable_submit.py tests/fault/test_commit_fail_no_send.py
```

Expect: pre-SUBMITTING txn contains intent+reservation+audit (+outbox iff event); adapter not called on commit/Risk failure.

### V3 — UNKNOWN no blind retry (SC-003)

```text
pytest tests/fault/test_timeout_unknown.py
```

Expect: reservation held; query/recon path; zero duplicate exposure.

### V4 — Recovery lock (SC-004)

```text
pytest tests/fault/test_startup_recovery.py
```

Expect: incomplete pagination/auth fail → not READY; KS not lowered; Recovery SEV1 queued.

### V5 — Strategy rule (SC-006)

```text
pytest tests/unit/test_rule_sma_cross_v1.py
```

Expect: crossover/exit/cooldown/ATR stop/abstain/long-only; closed candle only.

### V6 — Telegram contract (SC-007)

```text
pytest tests/integration/test_telegram_outbox.py tests/unit/test_telegram_commands.py tests/unit/test_telegram_digest.py
```

Expect: Owner test message; update_id dedup; wrong chat reject; TTL 60s; delivery retry/dead-letter; daily digest fields; mode tags; redaction.

### V7 — Full D1a fault matrix slice (§18.2 named rows)

```text
pytest -m d1a
```

Expect named D1a faults green (crash-before/after commit, UNKNOWN timeout, partial+protection, cancel+late, dup fills, disconnect, stale, disk/SAFE_LOCK, KS restart, Telegram 4xx, clock jump, orphans); §18.3 #1–#5,#7–#8; attach report paths into capability matrix Evidence cells.

## Import boundary check

```text
# Strategy/Risk/OMS must not import venue SDKs (CCXT etc.)
pytest tests/unit/test_import_boundaries.py
```

## Out of scope here

- CCXT DEMO soak, PySide6 installer, LIVE gates, Backtest, AI — see plan “Later phases”.

## Contracts reference

- [contracts/broker-adapter.md](./contracts/broker-adapter.md)
- [contracts/oms-submit-protocol.md](./contracts/oms-submit-protocol.md)
- [contracts/telegram-notify.md](./contracts/telegram-notify.md)
