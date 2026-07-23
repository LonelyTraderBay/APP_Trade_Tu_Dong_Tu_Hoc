---
description: "Task list for D1b CCXT DEMO Allowlist implementation"
---

# Tasks: D1b CCXT DEMO Allowlist

**Input**: Design documents from `/specs/002-d1b-ccxt-demo/`  
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [data-model.md](./data-model.md), [research.md](./research.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included (spec FR-008, SC-001…007, quickstart V0–V9, plan evidence gates).  
**Phase guard**: D1b only — one allowlist tuple (`binance`/spot/Binance Spot Testnet/`BTC/USDT`/`15m`). No LIVE enablement, no multi-exchange, no PySide6 Broker Hub/installer, no AI/ML/`ai_*`, no FastAPI/localhost HTTP. Do **not** change D1a UNKNOWN/Risk/OMS invariants.

**Implement gate (Owner)**: `/speckit-implement` and DEMO trading code merge **wait** until PR #5 (D1a) is on `main` and this branch is rebased (spec FR-012). Spec/plan/tasks may exist before that; T001 is the hard stop.

**Retry policy (do not conflate)**:
- **OMS/order path**: after `UNKNOWN`, query/recon only — **MUST NOT** blind re-place.
- **Telegram outbox**: transient delivery MAY retry; permanent 4xx → dead-letter (unchanged from D1a).

**Evidence split**:
- Contract + fault = mock/inject OK; **do not** count toward ≥50.
- ≥50 lifecycles + ≥72h soak = **real Binance Spot Testnet only**.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Parallelizable (different files; no unfinished blockers)
- **[USn]**: User story label (story phases only)

---

## Phase 1: Setup — Baseline + CCXT dep + skeleton

**Purpose**: Lock D1a baseline, add D1b dependency/layout without trading logic yet  
**Independent Test**: Branch rebased on merged D1a; `ccxt` importable; `pytest -m d1a` still collects/passes; no LIVE/UI deps added

- [x] T001 Verify PR #5 (D1a) is merged to `main`, then rebase/reset branch `002-d1b-ccxt-demo` onto that `main` (block all later tasks until done)
- [x] T002 Add pinned `ccxt` to `pyproject.toml` + regenerate hashed `uv.lock`; keep forbidding PySide6/scikit-learn/sqlite-vec/FAISS/MetaTrader5/FastAPI
- [x] T003 [P] Create package dirs `src/autotrade/core/adapters/ccxt_demo/`, `src/autotrade/core/certify/`, `src/autotrade/core/accounts/` and `tests/evidence/` per [plan.md](./plan.md)
- [x] T004 [P] Add pytest marker `d1b` in `pyproject.toml` and document `AUTOTRADE_D1B_REAL=1` gate in `specs/002-d1b-ccxt-demo/quickstart.md` (no secrets)
- [x] T005 Run smoke: install lockfile, `import ccxt`, `ruff check src tests`, `pytest -m d1a` (must stay green before DEMO code)

**Checkpoint**: Setup green — foundational schema/allowlist may begin

---

## Phase 2: Foundational — Allowlist, schema, registry, isolation

**Purpose**: Shared allowlist + D1b migration + adapter registry + import boundaries blocking all stories  
**⚠️ CRITICAL**: No US work until this phase completes

- [x] T006 Implement locked allowlist tuple constants/value object (`binance|spot|binance_spot_testnet|BTC/USDT|15m`) in `src/autotrade/core/domain/allowlist.py`
- [x] T007 [P] Extend SQLAlchemy models for `accounts.is_active`, DEMO mode fields, and new `certification_records` (+ optional `lifecycle_evidence`/`soak_runs`) in `src/autotrade/persistence/models/` per [data-model.md](./data-model.md)
- [x] T008 Write Alembic migration `0002_d1b_certify_allowlist` (no `ai_*`) in `src/autotrade/persistence/alembic/versions/`
- [x] T009 [P] Add schema/migration tests for D1b tables + single-active invariant helpers in `tests/unit/test_schema_d1b_certify.py`
- [x] T010 Implement certification record load/save/invalidate API in `src/autotrade/core/certify/records.py` per `contracts/certification-evidence.md`
- [x] T011 [P] Implement single-active account switch preconditions (flat / no open recon / no UNKNOWN) in `src/autotrade/core/accounts/active.py` per `contracts/account-switch.md`
- [x] T012 Implement built-in adapter registry (Paper + ccxt_demo only; refuse uncertified exchange) in `src/autotrade/core/adapters/registry.py`
- [x] T013 [P] Extend import-boundary tests so `strategy`/`risk`/`oms` never import `ccxt` (only `adapters/ccxt_demo` may) in `tests/unit/test_import_boundaries.py`
- [x] T014 [P] Add unit tests for allowlist accept/reject matrix in `tests/unit/test_allowlist.py`

**Checkpoint**: Foundation ready — US1 may start

---

## Phase 3: User Story 1 — Bind & trade certified DEMO tuple (P1) 🎯 MVP

**Goal**: Headless/CLI configures DEMO secrets, Test connection, enable only locked tuple; strategy on `BTC/USDT` `15m` uses same Risk→durable intent→OMS path; LIVE/other venues refused  
**Independent Test**: Mocked DEMO path places only allowlisted orders with durable intent before send; negatives refuse before network; CLI status redacts secrets  
**Maps**: Spec US1 · FR-001…007,010,011 · `contracts/allowlist-tuple.md`, `ccxt-demo-adapter.md`, `cli-demo-ops.md`

### Tests (write first — must FAIL before impl)

- [x] T015 [P] [US1] Contract tests for allowlist negatives (wrong exchange/symbol/TF/LIVE/production endpoint) in `tests/contract/test_allowlist_tuple.py`
- [x] T016 [P] [US1] Contract tests for CCXT DEMO adapter port (place/cancel/query_by_client_id/pagination/sandbox guard) with mock exchange in `tests/contract/test_ccxt_demo_adapter.py`
- [x] T017 [P] [US1] Integration test durable submit before mocked CCXT send + commit-fail no-send in `tests/integration/test_durable_submit_demo.py`
- [x] T018 [P] [US1] Fault test DEMO timeout → UNKNOWN → query/recon **no blind retry** in `tests/fault/test_demo_timeout_unknown.py`

### Implementation

- [x] T019 [US1] Implement Binance Spot Testnet sandbox guard (refuse LIVE/production hosts) in `src/autotrade/core/adapters/ccxt_demo/sandbox.py`
- [x] T020 [US1] Implement CCXT DEMO manifest + adapter (`connect`, OHLCV closed candles, place/cancel/query, opens/executions, positions/balances, protection best-effort) in `src/autotrade/core/adapters/ccxt_demo/manifest.py` and `src/autotrade/core/adapters/ccxt_demo/adapter.py`
- [x] T021 [US1] Wire DEMO candle ingest for `BTC/USDT` `15m` closed-only into existing market/features path in `src/autotrade/core/market/candles.py` (and thin DEMO fetch helper under `ccxt_demo/` if needed)
- [x] T022 [US1] Bind `rule_sma_cross_v1` to DEMO account symbol/TF via strategy_bindings helpers (no strategy code importing `ccxt`) — touch `src/autotrade/core/strategy/` only if binding helpers required; prefer account/binding service beside `src/autotrade/core/accounts/`
- [x] T023 [US1] Wire OMS/runtime to select active adapter (Paper vs ccxt_demo) without changing submit/UNKNOWN protocol in `src/autotrade/core/runtime.py` and `src/autotrade/core/oms/submit.py` (adapter injection only)
- [x] T024 [US1] Extend headless CLI: store DEMO keyring creds, `test-connection`, `enable-demo`/`disable-demo`, `status` (redacted) in `src/autotrade/entrypoints/headless.py` per `contracts/cli-demo-ops.md`
- [x] T025 [US1] Ensure Telegram compose/status tags active `mode=DEMO|PAPER` in `src/autotrade/core/notify/compose.py` (and command handlers if needed)
- [x] T026 [US1] Gate DEMO trading READY on allowlist + sandbox + credentials + **valid certification required** (no cert-pending trading); refuse LIVE in `src/autotrade/core/oms/account_state.py` / certify hooks
- [x] T027 [US1] Make T015–T018 PASS with implementation; confirm `pytest -m d1a` still green

**Checkpoint**: US1 MVP — DEMO path fail-closed on allowlist; durable submit preserved

---

## Phase 4: User Story 2 — Contract, fault, lifecycle ≥50, soak ≥72h (P1)

**Goal**: Certification evidence pack — contract + fault (mock OK), then real-testnet ≥50 round-trips + ≥72h wall-clock soak with 0 unresolved recon  
**Independent Test**: Mock suites green; with `AUTOTRADE_D1B_REAL=1` + keyring, evidence log shows ≥50 DONE round-trips and soak metadata; mock runs excluded from count  
**Maps**: Spec US2 · FR-008/009 · `contracts/certification-evidence.md` · quickstart V5–V8

### Tests / harnesses (write first where applicable)

- [x] T028 [P] [US2] Expand D1b fault matrix tests (disconnect, rate-limit, duplicate/out-of-order exec, auth fail) in `tests/fault/test_demo_fault_matrix.py`
- [x] T029 [P] [US2] Unit/contract tests for certification valid/invalidate rules in `tests/contract/test_certification_records.py`
- [x] T030 [US2] Evidence harness counting only real-testnet round-trip-to-flat lifecycles in `tests/evidence/test_demo_lifecycles_real.py` (skip unless `AUTOTRADE_D1B_REAL=1`)
- [x] T031 [US2] Soak harness/recorder (≥72h wall-clock, fail on Owner pause, allow clean sleep/resume) in `tests/evidence/test_demo_soak_real.py` and/or `src/autotrade/core/certify/soak.py` (skip unless real env)

### Implementation

- [x] T032 [US2] Implement lifecycle evidence recorder (source=`real_testnet` only; exclude mock) in `src/autotrade/core/certify/lifecycle.py`
- [x] T033 [US2] Implement soak run state machine (start/end, pause→fail continuous gate, recon end-check) in `src/autotrade/core/certify/soak.py`
- [x] T034 [US2] Implement certify CLI/workflow: record contract/fault pass timestamps; promote `certification_records.valid` only when gates met — extend `src/autotrade/core/certify/records.py` + `src/autotrade/entrypoints/headless.py`
- [x] T035 [US2] Invalidate certification on ccxt/app/endpoint/instrument/credential-scope change in `src/autotrade/core/certify/invalidate.py`
- [x] T036 [US2] Document Owner runbook for V7/V8 (no secrets) in `specs/002-d1b-ccxt-demo/quickstart.md` and ensure harness outputs evidence paths for matrix
- [x] T037 [US2] Make T028–T029 PASS; run T030/T031 attended on real testnet when Owner ready (D0-06 done); record results into cert tables / evidence files under gitignored path

**Checkpoint**: US2 — certification evidence path complete (real gates Owner-attended)

---

## Phase 5: User Story 3 — Keep Paper + D1a invariants (P2)

**Goal**: Paper profile retained; CLI switch Paper↔DEMO one-active; D1a regression green; no concurrent trading; no LIVE  
**Independent Test**: `pytest -m d1a` PASS; switch tests PASS; concurrent activate refused  
**Maps**: Spec US3 · FR-005/012 · `contracts/account-switch.md` · quickstart V0/V4

### Tests

- [x] T038 [P] [US3] Integration tests for Paper↔DEMO switch happy path + refuse non-flat/open recon/UNKNOWN in `tests/integration/test_account_switch.py`
- [x] T039 [P] [US3] Regression guard: phase boundary still refuses LIVE / second exchange in `tests/unit/test_phase_boundary_d1b.py`

### Implementation

- [x] T040 [US3] Wire CLI `switch-account paper|demo` to `src/autotrade/core/accounts/active.py` in `src/autotrade/entrypoints/headless.py`
- [x] T041 [US3] Ensure Paper adapter + bindings still work when DEMO code present (no removal of Paper paths) — verify via `src/autotrade/core/adapters/paper.py` + registry
- [x] T042 [US3] Make T038–T039 PASS; run full `pytest -m d1a` and `pytest -m d1b` (non-real) green

**Checkpoint**: US3 — Paper retained; single-active enforced

---

## Phase 6: Polish & Cross-Cutting

**Purpose**: Matrix evidence, docs sync, final quickstart sweep

- [x] T043 [P] Fill `docs/mvp-capability-matrix.md` Evidence for G1.1/G1.3, ADR-D09, D1b exit (versions, tuple, report paths) — leave LIVE empty
- [x] T044 [P] Sync any D1b notes in `AGENTS.md` if needed (no secret values)
- [x] T045 Run full non-real quickstart V0–V6 + V9 from `specs/002-d1b-ccxt-demo/quickstart.md`; confirm ruff clean
- [x] T046 Owner checklist: D0-06 ToS done before real V7/V8; confirm no secrets in git (`git status` / secret scan)
- [x] T047 Final review: no PySide6 UI, no LIVE enable, no second exchange, UNKNOWN/Risk/OMS unchanged

**Checkpoint**: D1b feature ready for PR (real soak/lifecycle evidence may attach as Owner artifacts)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: Starts with **T001 merge/rebase gate** — blocks everything if PR #5 not merged
- **Phase 2 Foundational**: Depends on Setup — **BLOCKS** all user stories
- **Phase 3 US1 (P1)**: Depends on Foundational — MVP DEMO path
- **Phase 4 US2 (P1)**: Depends on US1 adapter/CLI existing (needs something to certify)
- **Phase 5 US3 (P2)**: Depends on Foundational; ideally after US1 registry/CLI switch hooks
- **Phase 6 Polish**: After desired stories; real V7/V8 can trail code-complete

### User Story Dependencies

- **US1**: After Phase 2 — no dependency on US2/US3
- **US2**: After US1 (adapter + durable path exist)
- **US3**: After Phase 2; integrates switch with US1 CLI; regression validates US1 did not break Paper

### Within Each Story

- Tests marked first MUST fail before implementation
- Sandbox/manifest before full adapter
- Adapter before OMS/runtime wire
- Cert record API before promote-valid workflow
- Mock suites before real-network harnesses

### Parallel Opportunities

- After T001–T002: T003 ∥ T004
- After models sketched: T009 ∥ T013 ∥ T014
- US1 tests: T015 ∥ T016 ∥ T017 ∥ T018
- US2 tests: T028 ∥ T029
- US3 tests: T038 ∥ T039
- Polish: T043 ∥ T044

---

## Parallel Example: User Story 1

```text
# After Foundational checkpoint — launch US1 failing tests together:
T015 tests/contract/test_allowlist_tuple.py
T016 tests/contract/test_ccxt_demo_adapter.py
T017 tests/integration/test_durable_submit_demo.py
T018 tests/fault/test_demo_timeout_unknown.py

# Then implement adapter stack (sequential after tests exist):
T019 sandbox.py → T020 adapter.py → T023 runtime wire → T024 CLI
```

---

## Parallel Example: User Story 2

```text
T028 tests/fault/test_demo_fault_matrix.py
T029 tests/contract/test_certification_records.py
# Real harnesses (Owner attended, after mock green):
T030 + T031 with AUTOTRADE_D1B_REAL=1
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001 merge/rebase gate  
2. Phase 1–2 Setup + Foundational  
3. Phase 3 US1 (mock DEMO path + CLI + allowlist)  
4. **STOP & VALIDATE**: quickstart V1–V4 style tests green; `pytest -m d1a` green  
5. Then US2 evidence + US3 switch/regression  

### Incremental Delivery

1. Setup + Foundational → allowlist/schema ready  
2. US1 → DEMO trading path (mock) — MVP demoable via CLI  
3. US2 → certification + real ≥50 / soak (Owner)  
4. US3 → Paper switch hardening + regression seal  
5. Polish → matrix evidence + PR  

### Notes for `/speckit-implement`

- Do **not** start T002+ trading work until T001 confirms D1a on `main`
- Never commit API keys, tokens, or Chat IDs
- Do not weaken UNKNOWN/Risk/OMS to “make CCXT easier”
- Real network tests default **skip** without `AUTOTRADE_D1B_REAL=1`

---

## Task count summary

| Phase | Tasks | Story |
|---|---|---|
| Phase 1 Setup | T001–T005 (5) | — |
| Phase 2 Foundational | T006–T014 (9) | — |
| Phase 3 US1 | T015–T027 (13) | US1 |
| Phase 4 US2 | T028–T037 (10) | US2 |
| Phase 5 US3 | T038–T042 (5) | US3 |
| Phase 6 Polish | T043–T047 (5) | — |
| **Total** | **47** | |

**Suggested MVP scope**: Phases 1–3 (through US1 / T027)  
**Format validation**: All tasks use `- [ ]`, `Tnnn`, optional `[P]`, story `[USn]` only in story phases, and include file paths.
