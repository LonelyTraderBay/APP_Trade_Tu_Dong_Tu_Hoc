# D1a Requirements Quality Checklist: MVP D1a Paper Core

**Purpose**: Validate completeness, clarity, consistency, and edge-case coverage of D1a
safety/OMS/recovery/Paper/Telegram/phase-boundary requirements in spec + plan — not
implementation behavior.
**Created**: 2026-07-23
**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md)
**Depth**: Standard (PR / pre-`/speckit-tasks` gate)
**Audience**: Spec/plan reviewer
**Focus**: Capital safety · OMS/UNKNOWN · Recovery · Paper determinism · Telegram · Phase boundary

## Capital Safety / Risk Reservation / Fail-Closed

- [ ] CHK001 Are 100% of exposure-increasing paths required to pass Risk + committed reservation before any broker send? [Completeness, Spec §FR-006, §SC-002]
- [ ] CHK002 Is fail-closed behavior specified when Risk rejects or reservation cannot commit (no send + auditable)? [Clarity, Spec §US2-AS1, §FR-006]
- [ ] CHK003 Are reduce-only / exit paths explicitly distinguished from entry limits (safety validator; not blocked as new entries)? [Consistency, Spec §FR-006, §US1-AS4]
- [ ] CHK004 Are kill-switch levels L1–L4, persistence across restart, and “no auto-downgrade” stated unambiguously? [Completeness, Spec §FR-007, §SC-004]
- [ ] CHK005 Is Telegram’s remote authority limited to L1 Pause (no remote resume/flatten/unlock) consistent between US2 and FR-007/FR-010? [Consistency, Spec §US2-AS5, §FR-007, §FR-010]
- [ ] CHK006 Are stale quote/account/instrument freshness failures required to block exposure increases (not warn-only)? [Coverage, Spec §Edge Cases, Plan Constraints]
- [ ] CHK007 Can “fail-closed” acceptance be measured via SC-002 / §18.3 #1 without vague language? [Measurability, Spec §SC-002]

## OMS Durable Intent + UNKNOWN / No Blind Retry

- [ ] CHK008 Is the pre-SUBMITTING atomic bundle fully enumerated (intent + reservation + audit; outbox iff event)? [Completeness, Spec §Clarifications Q2, §FR-008]
- [ ] CHK009 Is “commit fail → no adapter call” stated for both exposure-increasing and reduce-only broker-bound submits? [Clarity, Spec §US3-AS1, §FR-008]
- [ ] CHK010 Are UNKNOWN / MAY_HAVE_BEEN_ACCEPTED semantics defined separately from inventing a reject? [Clarity, Spec §US3-AS2, Plan §Durable submit]
- [ ] CHK011 Is blind retry explicitly forbidden after post-send uncertainty, with query/recon as the required next step? [Completeness, Spec §FR-008, §SC-003]
- [ ] CHK012 Is reservation hold-until-recon required under UNKNOWN (must not early-release)? [Consistency, Spec §US3-AS2, data-model Reservation states]
- [ ] CHK013 Are crash-before-commit vs crash-after-commit/before-send distinguished in requirements (not lumped)? [Coverage, Spec §Edge Cases, Plan §11.1 mapping, contracts/oms-submit-protocol]
- [ ] CHK014 Does SC-003 quantify “zero duplicate exposure” and “never blind-retry” as objective pass/fail? [Measurability, Spec §SC-003]

## Recovery & Recon / SAFE_LOCK

- [ ] CHK015 Are Startup Recovery prerequisites for READY listed (pagination complete, fresh data, no unresolved breaks)? [Completeness, Spec §FR-009, §US3-AS3]
- [ ] CHK016 Are incomplete-recovery triggers enumerated (missing data, auth/connect fail, incomplete pagination, unresolved/stale breaks)? [Clarity, Spec §Clarifications Q3, §FR-009]
- [ ] CHK017 Is account state on incomplete recovery specified as not READY / RECOVERING or SAFE_LOCK with exposure increases blocked? [Clarity, Spec §US3-AS3]
- [ ] CHK018 Is “broker = current exposure truth; SQLite history immutable” stated without contradiction elsewhere? [Consistency, Spec §FR-009, §SC-005, Plan Truth boundaries]
- [ ] CHK019 Are orphan / missed-fill recon outcomes required (safe lock, provenance, no blind overwrite of intent/audit)? [Edge Case, Spec §US3-AS4, §SC-005]
- [ ] CHK020 Is disk full / DB integrity / mandatory commit failure mapped to SAFE_LOCK (or equivalent lock) in requirements? [Coverage, Spec §Edge Cases, Plan ADR-D03 constraints]
- [ ] CHK021 Does SC-004 make incomplete recovery objectively testable (KS not lowered, not READY, READY only after success criteria)? [Measurability, Spec §SC-004]

## Paper Determinism + Feature Schema + Closed Candle

- [ ] CHK022 Is bit-for-bit determinism under identical seed/config/candles an explicit requirement? [Completeness, Spec §SC-001, §FR-003]
- [ ] CHK023 Is happy-path Paper fill policy explicit (full fill + fee/slippage; no OHLC liquidity inference)? [Clarity, Spec §Clarifications Q1, §FR-003]
- [ ] CHK024 Are partial/late fills confined to fault injection (or explicit size fixtures) and forbidden from OHLC inference? [Consistency, Spec §Clarifications Q1, §Edge Cases]
- [ ] CHK025 Is `feature_schema_version` mandatory on feature snapshots used by Strategy? [Completeness, Spec §FR-004]
- [ ] CHK026 Are open/incomplete candles forbidden as signal inputs (closed candle only; abstain on insufficient/gap/stale)? [Completeness, Spec §FR-004, §US1-AS3, §SC-006]
- [ ] CHK027 Are `rule_sma_cross_v1` defaults (N_fast/N_slow/ATR/k/cooldown, spot long-only) specified without conflicting “Owner may change” language? [Consistency, Spec §FR-005, Assumptions]
- [ ] CHK028 Is the D1a instrument required to be a synthetic internal id (not a real venue symbol hard-code)? [Clarity, Spec §Clarifications Q5, §FR-005, §FR-016]
- [ ] CHK029 Can look-ahead prohibition and long-only/cooldown/abstain behaviors be measured via SC-006? [Measurability, Spec §SC-006]

## Telegram Safety (Commands, Redaction, Mode Tagging)

- [ ] CHK030 Is the inbound command allowlist exactly `/status`, `/pnl`, `/pause` with other mutations refused? [Completeness, Spec §FR-010, §SC-007]
- [ ] CHK031 Are wrong chat/user rejection, `update_id` dedup, and **60s** command TTL specified with audit on reject? [Clarity, Spec §Clarifications Q4, §FR-010]
- [ ] CHK032 Are outbox retry vs permanent-4xx dead-letter rules defined without implying “never drop source events”? [Clarity, Spec §FR-010, §Edge Cases]
- [ ] CHK033 Is mode tagging required on **100%** of outbound messages (at least PAPER in D1a) plus account identity? [Completeness, Spec §US4-AS6, §SC-007]
- [ ] CHK034 Are secret/PIN/token redaction requirements covering journal, logs, Telegram payloads, fixtures, and tests? [Coverage, Spec §FR-013, §SC-008]
- [ ] CHK035 Is “Telegram not configured / wrong credentials” behavior defined so trading stays fail-closed and process does not enter unsafe READY? [Edge Case, Spec §Edge Cases]
- [ ] CHK036 Are SC-007 and SC-008 objectively measurable for Telegram safety and redaction? [Measurability, Spec §SC-007, §SC-008]

## Phase Boundary (No CCXT / UI / AI / LIVE Leakage into D1a)

- [ ] CHK037 Does Out of Scope explicitly exclude CCXT/DEMO trading, full PySide6 UI/installer, LIVE, Backtest UI, AI/ML/`ai_*`, and localhost HTTP? [Completeness, Spec §Out of Scope]
- [ ] CHK038 Does the plan Forbidden list align with Spec Out of Scope (no CCXT trading, no full PySide6, no ML/vector, no FastAPI/Electron)? [Consistency, Plan Technical Context, Spec §Out of Scope]
- [ ] CHK039 Is LIVE hard-disable in D1a required as a product rule (not deferred silently to D1c)? [Clarity, Spec §FR-011, §US1-AS5]
- [ ] CHK040 Is “no `ai_*` schema in D1a” stated in both FR-002 and plan/data-model? [Consistency, Spec §FR-002, Plan Structure, data-model.md]
- [ ] CHK041 Is soak ≥14 days explicitly **not** a D1a exit criterion (and not a profit proof)? [Clarity, Spec §SC-010, §Out of Scope]
- [ ] CHK042 Are “later phases” in the plan limited to short placeholders without sneaking D1b/D1c/D3/D4 design into this artifact? [Boundary, Plan §Later phases]
- [ ] CHK043 Does Constitution Check in the plan claim D1a-only scope without merging gates? [Consistency, Plan §Constitution Check]

## Cross-Cutting Traceability & Ambiguities

- [ ] CHK044 Are Spec Clarifications Q1–Q5 reflected in FR/SC/Edge Cases without leftover contradictory wording? [Consistency, Spec §Clarifications]
- [ ] CHK045 Are capability-matrix Evidence expectations for D1a rows named (what must be recorded to claim pass)? [Completeness, Spec §SC-009, Plan §Test layout]
- [ ] CHK046 Is ADR-D03.1 table completeness required before D1a exit without inventing `ai_*`? [Completeness, Plan §Schema ADR-D03.1, data-model.md]
- [ ] CHK047 Are any remaining vague adjectives (“robust”, “proper”, “as needed”) left in safety-critical FR/SC that lack metrics? [Ambiguity, Gap]
- [ ] CHK048 Is the assumption that D1a may use local KS/Telegram hooks without full UI documented and non-conflicting with “Telegram mandatory”? [Assumption, Spec §Assumptions, §FR-010]

## Notes

- How to use: mark `[x]` when the **requirements text** adequately answers the question; if not, fix spec/plan (not code).
- Traceability target: items cite Spec FR/SC/US/Clarifications, Plan sections, or Gap/Ambiguity/Assumption markers.
- Related checklist: [requirements.md](./requirements.md) (general spec quality); this file is the D1a safety/phase gate list.
- 2026-07-23 remediation: analyze HIGH C1–C4 closed in `tasks.md`/`spec.md`/`plan.md` (named §18.2 faults, digest, test-message, protection, OMS vs notify retry). Re-check CHK items against updated artifacts before `/speckit-implement`.
