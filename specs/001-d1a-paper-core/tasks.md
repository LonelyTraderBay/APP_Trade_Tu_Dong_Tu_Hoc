---
description: "Task list for D1a Paper Core implementation"
---

# Tasks: MVP D1a Paper Core

**Input**: Design documents from `/specs/001-d1a-paper-core/`  
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [data-model.md](./data-model.md), [research.md](./research.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included (spec FR-014, plan §18 exit, quickstart).  
**Phase guard**: No CCXT trading, PySide6 UI, AI/ML/`ai_*`, LIVE enablement, FastAPI, or localhost HTTP tasks.

**Retry policy (do not conflate)**:
- **OMS/order path**: after `UNKNOWN`, query/recon only — **MUST NOT** blind re-place the order.
- **Telegram outbox**: transient delivery failures MAY retry with backoff; permanent 4xx → dead-letter (source journal retained).

**Owner groups → phases**: T0→Phase1 · T1→Phase2 · T2+T3→US1 · T4→US2 · T5+T6→US3 · T7→US4 · T8→Polish

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Parallelizable (different files; no unfinished blockers)
- **[USn]**: User story label (story phases only)

---

## Phase 1: Setup — T0 D1a-00 Runtime Pin + Smoke

**Purpose**: Pin one CPython minor + hashed lockfile; Windows smoke before trading code  
**Independent Test**: `ruff check` + `pytest --collect-only` on allowlisted imports; ADR-D01 evidence note in matrix

- [ ] T001 Create package skeleton dirs `src/autotrade/{entrypoints,core/{domain,adapters,market,features,strategy,risk,oms,ledger,notify},persistence}` and `tests/{unit,contract,integration,fault}` per plan §13
- [ ] T002 Add `pyproject.toml` with closed CPython range candidate `>=3.14,<3.15`, D1a deps only (SQLAlchemy 2.x, Alembic, keyring, python-telegram-bot, pytest, ruff) and package `src/autotrade`
- [ ] T003 Generate hashed lockfile (e.g. `uv.lock` or `requirements.txt` with hashes) for D1a allowlist; exclude CCXT/PySide6/scikit-learn/sqlite-vec/FAISS
- [ ] T004 [P] Add `.gitignore` entries for `data/`, `.venv/`, `%LOCALAPPDATA%` mirrors, pytest/ruff caches, and evidence reports
- [ ] T005 [P] Add minimal `src/autotrade/__init__.py` and headless stub `src/autotrade/entrypoints/headless.py` (no HTTP listener)
- [ ] T006 Run Windows smoke: create venv, install lockfile, import allowlisted packages, `ruff check src tests`, `pytest --collect-only`; if 3.14.x fails document fallback 3.13/3.12 in `specs/001-d1a-paper-core/plan.md` and `docs/mvp-capability-matrix.md` ADR-D01 Evidence **before** later phases

**Checkpoint**: D1a-00 green — trading modules may begin

---

## Phase 2: Foundational — T1 Domain + Persistence ADR-D03.1

**Purpose**: Shared domain ports + SQLite WAL schema (all ADR-D03.1 tables, no `ai_*`) blocking all stories  
**⚠️ CRITICAL**: No US work until this phase completes

- [ ] T007 Implement Clock ports (UTC wall + monotonic) and ID factories in `src/autotrade/core/domain/clock.py` and `src/autotrade/core/domain/ids.py`
- [ ] T008 [P] Implement Decimal money/qty types and redaction helpers in `src/autotrade/core/domain/money.py` and `src/autotrade/core/domain/redaction.py`
- [ ] T009 [P] Implement keyring secret-ref helpers (no plaintext) in `src/autotrade/persistence/secrets.py`
- [ ] T010 Configure SQLAlchemy engine (WAL, `synchronous=FULL`, `foreign_keys=ON`, busy_timeout) in `src/autotrade/persistence/engine.py` with paths for `%LOCALAPPDATA%/AutoTradeAI/` and dev `data/`
- [ ] T011 Define SQLAlchemy models for all ADR-D03.1 tables (no `ai_*`) in `src/autotrade/persistence/models/`
- [ ] T012 Initialize Alembic and write migration creating ADR-D03.1 schema in `src/autotrade/persistence/alembic/`
- [ ] T013 Implement pre-migration snapshot + integrity_check backup hook in `src/autotrade/persistence/backup.py`
- [ ] T014 [P] Add unit tests for Decimal/clock/redaction in `tests/unit/test_domain_primitives.py`
- [ ] T015 Add migration/roundtrip test asserting all ADR-D03.1 tables exist and no `ai_*` in `tests/unit/test_schema_adr_d03_1.py`
- [ ] T016 [P] Add unit tests for `pin_verifier` Argon2id hash + lockout counters (schema usable; full Settings UI deferred to D1c) in `tests/unit/test_pin_verifier.py` and `src/autotrade/persistence/pin.py`
- [ ] T017 Wire single-writer session/uow helper for atomic txns in `src/autotrade/persistence/uow.py`
- [ ] T018 Implement asyncio composition root + OMS command-owner queue stub (no localhost HTTP) in `src/autotrade/entrypoints/headless.py` and `src/autotrade/core/runtime.py`

**Checkpoint**: Foundation ready — US1 may start

---

## Phase 3: User Story 1 — Paper Path (T2 Adapter + T3 Market/Strategy) 🎯 MVP

**Goal**: Deterministic Paper loop: closed candles → features → `rule_sma_cross_v1` → (later Risk/OMS) with Fake/Paper adapter  
**Independent Test**: Seeded candle replay yields identical signals; Paper happy-path full fills; import boundary forbids venue SDKs in strategy package  
**Maps**: Spec US1 · contracts/broker-adapter.md

### T2 — Fake/Paper adapter + contract stubs

- [ ] T019 [US1] Define Broker Adapter Interface + Paper manifest in `src/autotrade/core/adapters/protocol.py` and `src/autotrade/core/adapters/manifest.py`
- [ ] T020 [US1] Implement FakeBroker/PaperAdapter (full fill + fee/slippage; fault-injection hooks; `upsert_protection`; no OHLC partial inference) in `src/autotrade/core/adapters/paper.py`
- [ ] T021 [P] [US1] Add contract tests for place/query/cancel/full-fill/pagination/client-id lookup/**protection upsert + failure**/injected partial-late hooks in `tests/contract/test_paper_adapter.py`
- [ ] T022 [P] [US1] Add import-boundary test ensuring `strategy`/`risk`/`oms` do not import CCXT or venue SDKs in `tests/unit/test_import_boundaries.py`

### T3 — Market / features / rule_sma_cross_v1

- [ ] T023 [US1] Implement synthetic instrument `PAPER-INTERNAL-1` cache helpers (normalized tick/lot/exposure fields for Risk) in `src/autotrade/core/market/instruments.py`
- [ ] T024 [P] [US1] Implement closed-candle store/ingest (reject open candles for signals) in `src/autotrade/core/market/candles.py`
- [ ] T025 [US1] Implement FeatureEngine with `feature_schema_version` snapshots in `src/autotrade/core/features/engine.py`
- [ ] T026 [US1] Implement `rule_sma_cross_v1` (defaults 10/30/ATR14/k=1.5/cooldown 3; spot long-only; abstain rules) in `src/autotrade/core/strategy/rule_sma_cross_v1.py`
- [ ] T027 [P] [US1] Add unit tests for SMA/ATR/cooldown/abstain/long-only/closed-candle in `tests/unit/test_rule_sma_cross_v1.py`
- [ ] T028 [US1] Add integration stub Strategy→features→signals only (not full OMS) in `tests/integration/test_paper_signal_replay.py`

**Checkpoint**: US1 MVP — deterministic signals + Paper adapter contracts green

---

## Phase 4: User Story 2 — Risk + Kill-Switch (T4)

**Goal**: Fail-closed Risk reservation; KS L1–L4 persist across restart; Telegram pause authority reserved for US4  
**Independent Test**: Rejected risk never sends; L2/L3/L4 survive restart without auto-downgrade  
**Maps**: Spec US2

- [ ] T029 [US2] Implement risk check + atomic reservation service in `src/autotrade/core/risk/engine.py`
- [ ] T030 [US2] Implement reduce-only / no-position-flip safety validator in `src/autotrade/core/risk/validators.py`
- [ ] T031 [US2] Implement KS L1–L4 state machine with DB persistence in `src/autotrade/core/risk/kill_switch.py`
- [ ] T032 [P] [US2] Add unit tests for reservation math, reject paths, KS scope/persist in `tests/unit/test_risk_and_ks.py`
- [ ] T033 [US2] Add restart persistence test (KS not auto-lowered) in `tests/fault/test_ks_persist_restart.py`

**Checkpoint**: US2 — risk/KS independently verifiable

---

## Phase 5: User Story 3 — OMS + Ledger + Recovery (T5 + T6)

**Goal**: Durable submit before network; UNKNOWN without blind order retry; protection lifecycle; Startup Recovery before READY  
**Independent Test**: Commit-fail never calls adapter; timeout→UNKNOWN→query; incomplete recovery stays locked  
**Maps**: Spec US3 · contracts/oms-submit-protocol.md

### T5 — OMS + ledger + durable submit + UNKNOWN + protection

- [ ] T034 [US3] Implement order intent FSM + delivery-certainty axis (`NOT_SENT`/`SENDING`/`CONFIRMED`/`MAY_HAVE_BEEN_ACCEPTED`) in `src/autotrade/core/oms/fsm.py`
- [ ] T035 [US3] Implement durable submit protocol (single txn: intent+reservation+audit[+outbox iff event] then SUBMITTING; assert rows land in `order_intents`/`risk_reservations`/`risk_checks`/`audit_events`) in `src/autotrade/core/oms/submit.py`
- [ ] T036 [US3] Implement `order_protection` lifecycle (attach/update qty on fills; failure → Paper flatten/lock path) in `src/autotrade/core/oms/protection.py`
- [ ] T037 [US3] Implement UNKNOWN path (hold reservation; query by client_id; **MUST NOT** re-place/blind-retry the order) in `src/autotrade/core/oms/unknown.py`
- [ ] T038 [US3] Implement fill ledger (idempotent `(account_id, broker_execution_id)`) in `src/autotrade/core/ledger/fills.py`
- [ ] T039 [P] [US3] Implement positions_local derived view + provenance in `src/autotrade/core/ledger/positions.py`
- [ ] T040 [P] [US3] Add unit/FSM tests for transitions and CAS guards in `tests/unit/test_oms_fsm.py`
- [ ] T041 [P] [US3] Add unit tests for protection qty sync / failure escalation in `tests/unit/test_order_protection.py`
- [ ] T042 [US3] Add integration test durable submit + Paper fill path (also asserts `signals`/`balances_snapshots`/`execution_cursors` written when exercised) in `tests/integration/test_durable_submit.py`
- [ ] T043 [US3] Add fault test mandatory commit-fail → no adapter call in `tests/fault/test_commit_fail_no_send.py`
- [ ] T044 [US3] Add fault test **crash before intent commit** → no broker request, no orphan reservation in `tests/fault/test_crash_before_commit.py`
- [ ] T045 [US3] Add fault test **crash after commit before/during send** → delivery `NOT_SENT` vs uncertain; uncertain queries, no blind order retry in `tests/fault/test_crash_after_commit.py`
- [ ] T046 [US3] Add fault test timeout → UNKNOWN / `MAY_HAVE_BEEN_ACCEPTED`, reservation held, zero duplicate exposure, no blind order retry in `tests/fault/test_timeout_unknown.py`

### T6 — Recovery / recon

- [ ] T047 [US3] Implement Startup Recovery checklist (§11.2 steps 1–10) for Paper in `src/autotrade/core/oms/recovery.py`
- [ ] T048 [US3] Implement continuous recon + execution cursor overlap/dedup in `src/autotrade/core/ledger/recon.py`
- [ ] T049 [US3] Persist/handle `recon_breaks` and SAFE_LOCK / not-READY gates in `src/autotrade/core/oms/account_state.py`
- [ ] T050 [US3] Add fault tests for incomplete recovery (auth fail, incomplete pagination, missing data → locked, KS not lowered) in `tests/fault/test_startup_recovery.py`
- [ ] T051 [P] [US3] Add fault tests for orphan/missed fill recon convergence (broker wins exposure; history intact; L2) in `tests/fault/test_recon_orphans.py`

**Checkpoint**: US3 — crash/UNKNOWN/recovery/protection invariants hold for Paper

---

## Phase 6: User Story 4 — Telegram Notify (T7)

**Goal**: Durable outbox; test message; daily digest; `/status|/pnl|/pause`; dedup/TTL/redaction/mode tags  
**Independent Test**: Test message OK; wrong chat rejected; update_id dedup; TTL 60s; digest fields; dead-letter on permanent 4xx; mode on all outbound  
**Maps**: Spec US4 · contracts/telegram-notify.md

- [ ] T052 [US4] Implement notify outbox repository (**delivery** retry/backoff/dead_letter — not OMS order retry) in `src/autotrade/core/notify/outbox.py`
- [ ] T053 [US4] Implement Telegram transport via python-telegram-bot + keyring token in `src/autotrade/core/notify/telegram_transport.py`
- [ ] T054 [US4] Implement Owner **test-message** (G5.1) send path in `src/autotrade/core/notify/telegram_transport.py` and wire from headless/settings hook in `src/autotrade/entrypoints/headless.py`
- [ ] T055 [US4] Implement inbound command handler (`/status|/pnl|/pause`, update_id dedup, 60s TTL, wrong chat/user reject+audit) in `src/autotrade/core/notify/commands.py`
- [ ] T056 [US4] Ensure `/pause` maps to KS L1 only (no remote resume/flatten/unlock) in `src/autotrade/core/notify/commands.py` and `src/autotrade/core/risk/kill_switch.py`
- [ ] T057 [US4] Implement message composer with mode+account tags and redaction in `src/autotrade/core/notify/compose.py`
- [ ] T058 [US4] Implement daily digest job (P&L, order counts, drawdown, KS, adapter health, as-of time; Owner local day) in `src/autotrade/core/notify/digest.py`
- [ ] T059 [P] [US4] Add unit tests for commands/TTL/dedup/allowlist in `tests/unit/test_telegram_commands.py`
- [ ] T060 [P] [US4] Add unit tests for digest payload fields + mode tags in `tests/unit/test_telegram_digest.py`
- [ ] T061 [US4] Add integration tests for test-message, outbox restart replay, **delivery** transient retry, permanent-4xx dead-letter (source events retained) in `tests/integration/test_telegram_outbox.py`
- [ ] T062 [P] [US4] Add redaction scan test (no secrets in payloads/fixtures) in `tests/unit/test_secret_redaction.py`

**Checkpoint**: US4 — Telegram safety (G5.1–G5.5) independently verifiable

---

## Phase 7: Polish — T8 Integration + Fault Matrix §18.2 (D1a rows)

**Purpose**: E2E path + named §18.2 D1a fault rows + evidence  
**Independent Test**: `pytest -m d1a` green; §18.3 #1–#5,#7–#8; matrix Evidence fillable; soak ≥14d **not** required

**§18.2 D1a required (must have named tests):** crash-before-commit; crash-after-commit; timeout UNKNOWN; partial+protection; cancel+late; dup/out-of-order; auth/disconnect (Paper injectable); stale; disk/SAFE_LOCK; KS restart; Telegram 429/4xx; sleep/clock jump; orphan recon.  
**Deferred (not D1a tasks):** real exchange rate-limit soak (D1b); §18.2 AI/D4 rows; LIVE protection-only rows (D1.1).

- [ ] T063 Add full-path integration Strategy→Risk→OMS→Paper→ledger→outbox in `tests/integration/test_strategy_risk_oms_paper.py`
- [ ] T064 [P] Add seeded Paper replay determinism test (bit-for-bit fills/balances) in `tests/integration/test_paper_replay_seed.py`
- [ ] T065 [P] Add fault test partial fill during protection create/update → qty sync or L3/lock in `tests/fault/test_partial_fill_protection.py`
- [ ] T066 [P] Add fault test cancel timeout + late fill → `CANCEL_UNKNOWN`, single fill ingest in `tests/fault/test_cancel_unknown_late_fill.py`
- [ ] T067 [P] Add fault test duplicate/out-of-order executions → unique fill, no state regression in `tests/fault/test_dup_out_of_order_fills.py`
- [ ] T068 [P] Add fault test Paper auth/disconnect injection → no new exposure-increasing entry; recon lane prioritized in `tests/fault/test_disconnect_no_entry.py`
- [ ] T069 [P] Add fault test stale quote/account/instrument → no exposure increase + notify stale correctly in `tests/fault/test_stale_fail_closed.py`
- [ ] T070 [P] Add fault test disk full/DB busy/corrupt/migration fail → SAFE_LOCK, no new submit in `tests/fault/test_disk_safe_lock.py`
- [ ] T071 [P] Add fault test sleep/resume or wall-clock jump → refresh + recovery subset before trade in `tests/fault/test_clock_jump_recovery.py`
- [ ] T072 Add pytest marker `d1a` on all D1a fault/integration exit tests + evidence report hook (versions/seed/config/results) in `tests/conftest.py`
- [ ] T073 Document Evidence cell fill instructions for D1a rows in `docs/mvp-capability-matrix.md` (leave Evidence blank until runs produce artifacts)
- [ ] T074 Run `ruff check src tests` and `pytest -m d1a` (unit/contract/integration/fault marked d1a); store report under gitignored evidence path
- [ ] T075 Verify LIVE hard-disabled and no CCXT/UI/AI modules added (boundary assert only) in `tests/unit/test_phase_boundary_d1a.py`

**Checkpoint**: D1a exit criteria met for Paper core

---

## Dependencies & Execution Order

### Phase dependencies

```text
T0 (Phase1) → T1 (Phase2) → US1 (T2+T3) → US2 (T4) → US3 (T5+T6) → US4 (T7) → T8 (Polish)
```

- **US2** needs US1 Paper adapter + domain persistence
- **US3** needs US2 Risk/KS for durable submit bundle
- **US4** needs US2 KS for `/pause`→L1; outbox table from T1
- **T8** needs US1–US4; named §18.2 faults may land after US3/US4 pieces they exercise

### Parallel opportunities (only marked [P] above)

- After T001–T003: T004 ∥ T005
- In T1: T008 ∥ T009; T014/T016 after primitives
- In US1: T021 ∥ T022 after T020; T024 ∥ T023; T027 after T026
- In US2: T032 after T029–T031
- In US3: T039 ∥ T038; T040 ∥ T041; T051 ∥ T050; crash/timeout faults after submit/UNKNOWN
- In US4: T059 ∥ T060 ∥ T062; T061 after transport/outbox
- In T8: T064–T071 parallel after fixtures ready; T074 after all `d1a` tests exist

### User story independent tests

| Story | Test focus |
|---|---|
| US1 | `test_rule_sma_cross_v1`, `test_paper_adapter` (incl. protection), signal replay |
| US2 | `test_risk_and_ks`, `test_ks_persist_restart` |
| US3 | durable submit, crash boundaries, UNKNOWN, protection, recovery/recon |
| US4 | test-message, commands/TTL, digest, outbox delivery retry/dead-letter, redaction |

---

## Implementation Strategy

### MVP first (US1 only)

1. Complete T0 + T1  
2. Complete US1 (T2+T3)  
3. **STOP** — validate deterministic Paper signals + adapter contracts  
4. Then US2 → US3 → US4 → T8

### Incremental delivery

1. T0 smoke evidence → matrix ADR-D01  
2. T1 schema evidence → ADR-D03.1  
3. Each story checkpoint before next  
4. T8 fills G2.3/G3/G4.1/G5/fault Evidence cells  

### Explicitly excluded (do not add tasks)

- CCXT DEMO / real exchange (D1b)  
- PySide6 UI / installer / toast UI chrome (D1c) — D1a notify channel is **Telegram outbox only**  
- LIVE / D1.1 gates  
- Backtest UI (D3) / AI/ML/vector/`ai_*` (D4)  
- FastAPI / localhost HTTP / Electron  

---

## Notes

- Commit after each logical group (T0, T1, each US, T8)  
- Prefer failing tests first within a story when adding `tests/` tasks  
- If Python fallback activates at T006, halt trading PRs until matrix/plan updated  
- Remediation 2026-07-23: closed analyze HIGH gaps C1–C4 (+ digest/test-message/protection/§18.2 named faults/PIN unit/retry wording)
