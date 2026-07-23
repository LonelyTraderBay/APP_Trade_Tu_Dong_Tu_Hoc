# Feature Specification: MVP D1a Paper Core

**Feature Branch**: `001-d1a-paper-core`

**Created**: 2026-07-23

**Status**: Draft

**Input**: User description: "Xây dựng MVP D1a của AutoTrade AI Desktop Solo theo Kien-truc-App-Desktop-Solo-v1.4.md và docs/mvp-capability-matrix.md — domain/journal/Paper/Risk/OMS/Recovery/Telegram; OUT: CCXT/UI/LIVE/AI."

## Clarifications

### Session 2026-07-23

- Q: Paper partial-fill fidelity (happy path vs OHLC inference) → A: Happy path = full fill (+ fee/slippage); partial/late only via fault injection (or explicit size fixtures). Never infer liquidity from OHLC.
- Q: Pre-SUBMITTING atomic commit bundle → A: Always intent + reservation + audit in one txn before SUBMITTING; notify_outbox iff that step creates an outbound event; commit fail → no send.
- Q: Recovery incomplete → account lock → A: Stay locked / not READY; block exposure increases; do not auto-lower KS; notify via outbox; READY only after full recovery success criteria.
- Q: Telegram inbound/outbound failure policy → A: Dedup update_id; wrong chat/user → reject+audit; command TTL 60s; transient → retry; permanent 4xx → dead-letter; journal retains source events.
- Q: D1a Paper symbol identity vs D1b exchange TBD → A: Synthetic internal id only for D1a (no real venue/symbol hard-code); timeframe Owner-configured; D1b binds real tuple after D0-11.
- Post-analyze remediation: SC-007 includes digest+test message; OMS UNKNOWN ≠ Telegram delivery retry; PIN unit in D1a; toast UI deferred to D1c.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deterministic Paper Trading Path (Priority: P1)

As the Owner, I run a single Paper account on one **synthetic internal** simulated symbol (not a real venue symbol) and one Owner-configured timeframe so that a rule-based strategy can produce closed-candle signals, size through Risk, and execute through a simulated broker without ever contacting a real exchange or assuming D0-11 is locked.

**Why this priority**: Proves the core value path (signal → risk → order → fill) that all later phases extend; without it D1a has no product outcome.

**Independent Test**: Feed a fixed candle series and seed; observe identical signals, orders, fills, and balances across two full runs; confirm no real-exchange traffic.

**Acceptance Scenarios**:

1. **Given** a Paper account with configured fee/slippage and a fixed seed, **When** the same closed-candle series is replayed twice, **Then** signals, reservations, orders, fills, and ending balances match exactly; happy-path fills are full fills (G2.3).
2. **Given** strategy `rule_sma_cross_v1` defaults (N_fast=10, N_slow=30, ATR14, k=1.5, cooldown 3, spot long-only), **When** a valid long crossover appears on a closed candle with no open long, **Then** an entry intent is proposed with protective stop distance derived from ATR×k and sizing delegated to Risk (G4.1, §07.3).
3. **Given** insufficient history, candle gap/out-of-order, or stale quote, **When** the strategy evaluates, **Then** it abstains (no entry signal).
4. **Given** an open long, **When** a bearish crossover closes, **Then** an exit follows the reduce-only safety path (not blocked as a new entry).
5. **Given** D1a runtime, **When** any LIVE enablement is attempted, **Then** LIVE remains hard-disabled (G2.4–G2.5).

---

### User Story 2 - Fail-Closed Risk and Kill-Switch (Priority: P2)

As the Owner, I rely on risk checks and kill-switch levels so the system never increases exposure without an approved reservation, and so Pause/lock states survive restart.

**Why this priority**: Capital safety outranks feature velocity; required before trusting unsupervised Paper loops.

**Independent Test**: Attempt entries that violate limits; trigger L1–L4; restart the app; verify exposures blocked/allowed as specified and KS level not auto-lowered.

**Acceptance Scenarios**:

1. **Given** a candidate that would increase exposure, **When** Risk rejects or reservation cannot commit, **Then** no order is sent and the rejection is auditable (G3.1).
2. **Given** an approved increase, **When** submit proceeds, **Then** every submit carries a risk-check identity tied to a committed reservation (G3.1).
3. **Given** L1 Pause, **When** new exposure-increasing entries are attempted, **Then** they are blocked while protection/exit management may continue (G3.2).
4. **Given** L2/L3/L4 latched, **When** the app restarts, **Then** the persisted level remains and trading does not become READY until recovery completes (G3.2, G3.6).
5. **Given** Telegram remote control in D1a, **When** `/pause` is accepted from the Owner chat, **Then** only L1 Pause is applied; resume/flatten/unlock are not available remotely (G3.2, G5.4).

---

### User Story 3 - Crash-Consistent Orders and Recovery (Priority: P3)

As the Owner, if the app crashes or a send times out after transmission may have started, I need the system to reconcile against the simulated broker without creating duplicate exposure or inventing rejects.

**Why this priority**: OMS/recovery correctness is the difference between a demo toy and a trustworthy trading core.

**Independent Test**: Inject crash/timeout/partial/late/duplicate fill and stale/disk faults from the fault matrix; assert no duplicate exposure and convergence to broker state.

**Acceptance Scenarios**:

1. **Given** an exposure-increasing or reduce-only submit, **When** the send path begins, **Then** `order_intents`, `risk_reservations`, and `audit_events` (plus `notify_outbox` if that step emits a notify) were committed in one durable transaction before `SUBMITTING`/adapter call (G3.3, ADR-D03.1).
2. **Given** timeout after transmission may have started, **When** the outcome is uncertain, **Then** delivery is treated as UNKNOWN, reservation is held, and the system queries/reconciles — it MUST NOT blind-retry (G3.3, §18.3).
3. **Given** startup after unclean shutdown **or** recovery with missing data, auth/connect fail, incomplete pagination, or unresolved breaks, **When** Startup Recovery runs, **Then** KS is restored without auto-downgrade, exposure increases stay blocked, the account remains not READY (RECOVERING/SAFE_LOCK as applicable), a Recovery failure/SEV1 is queued when recovery cannot complete, and READY occurs only after pagination complete, fresh data, and no unresolved breaks (G3.6, §11.2).
4. **Given** continuous or startup recon, **When** local and broker views disagree (orphan order/position, missed fill), **Then** broker current exposure wins, history/intent/audit are not blindly overwritten, and the account moves to a safe lock until resolved (G3.4, §18.3).
5. **Given** any certified D1a fault scenario (crash, timeout, partial fill, stale data, disk pressure, KS persist), **When** the suite runs, **Then** invariants §18.3 #1–#5, #7–#8 hold and evidence is recordable (capability matrix fault rows).

---

### User Story 4 - Mandatory Telegram Operations Channel (Priority: P4)

As the Owner, I receive event-driven Telegram reports and can query status/P&L or Pause remotely, without secrets leaking and without confusing Paper with other modes.

**Why this priority**: Solo desktop ops need an attended channel; constitution and G5 make Telegram mandatory in D1a.

**Independent Test**: Configure bot credentials via OS secret store; trigger events; verify outbox survives restart; reject wrong chat/user; confirm redaction and mode tags.

**Acceptance Scenarios**:

1. **Given** valid Owner bot configuration, **When** a test message is requested, **Then** delivery succeeds to the private chat (G5.1).
2. **Given** inbound messages from a non-Owner chat or user, **When** they arrive, **Then** they are rejected, audited, and their `update_id` is persisted for dedup (G5.1, G5.4).
3. **Given** trading/risk/kill-switch events, **When** they occur, **Then** corresponding push notifications are queued durably; transient delivery failures retry with bounded backoff; permanent 4xx moves the outbox item to dead-letter without deleting the source journal event (G5.2, ADR-D04).
4. **Given** end of local day, **When** digest is due, **Then** Owner receives P&L, order counts, drawdown, KS, and adapter health with data-as-of time (G5.3).
5. **Given** D1a remote commands, **When** Owner sends `/status`, `/pnl`, or `/pause`, **Then** they are handled with `update_id` persistence/dedup; commands older than **60s TTL** are rejected and audited; other mutation commands are refused (G5.4).
6. **Given** any outbound Telegram text, **When** it is composed, **Then** it includes mode (at least PAPER in D1a) and account identity, and never contains raw secrets/PIN/token (G5.5, §18.3 #8).

---

### Edge Cases

- Paper happy-path fills are **full fills** with configured fee/slippage only; the system MUST NOT infer liquidity or partial-fill sizes from OHLC alone (G2.3).
- Partial/late fills appear only via explicit fault injection (or explicit bid/ask size fixtures if later added); during protection attach/update, protection quantity tracks fill and failure escalates to safe flatten/lock for Paper.
- Duplicate delivery of the same fill: only one economic effect.
- Quote/candle stale or clock skew beyond policy: fail-closed (no new exposure); account not READY.
- Disk full / journal write failure mid-commit: no SUBMITTING/send; recoverable error surfaced; no partial “sent without durable intent.”
- Mandatory pre-SUBMITTING commit fails → adapter MUST NOT be called.
- Strategy cooldown window after exit: no new entries for M closed candles (default 3).
- Short signals on spot long-only Paper: ignored/abstained.
- Simultaneous local Pause and Telegram `/pause`: effective KS is the highest required level; no auto-downgrade on restart.
- Recovery missing data, auth/connect fail, incomplete pagination, or stale/unresolved breaks: account stays locked / not READY; no exposure increase; KS not auto-lowered; Recovery failure/SEV1 via outbox.
- Telegram command older than 60s TTL, or from wrong chat/user: reject + audit; `update_id` still persisted for dedup.
- Telegram outbox: transient failures retry with bounded backoff; permanent 4xx → dead-letter; source events remain in the journal.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide domain types and clock/identity ports using UTC time, monotonic durations for timeouts, and exact decimal money/quantity semantics (ADR-D12).
- **FR-002**: System MUST persist trading state in a durable local journal with migration-managed schema covering the minimum trading tables of ADR-D03.1 and MUST NOT create AI learning tables in D1a.
- **FR-003**: System MUST expose a Fake/Paper broker adapter that never sends real exchange orders, applies configured fee and slippage, yields identical results for identical inputs and seed, uses **full fills** on the happy path, and MUST NOT infer liquidity/partial fills from OHLC; partial/late fills ONLY via fault injection or explicit size fixtures (G2.3).
- **FR-004**: System MUST compute versioned features from closed candles only and MUST tag snapshots with `feature_schema_version` (§07.4).
- **FR-005**: System MUST implement strategy rule `rule_sma_cross_v1` with defaults N_fast=10, N_slow=30, ATR period 14, k=1.5, cooldown M=3, spot long-only, on exactly one **synthetic internal** instrument id (e.g. `PAPER-INTERNAL-1`) and one Owner-configured timeframe. D1a MUST NOT hard-code a real exchange venue or venue symbol as if D0-11 were decided; D1b binds the certified tuple later (G4.1, §07.3, mục 16).
- **FR-016**: Instrument metadata for D1a Paper MUST be clearly marked internal/simulated; Strategy/Risk/OMS MUST depend only on normalized internal instrument fields, never on assumed live venue identifiers.
- **FR-006**: System MUST route 100% of exposure-increasing actions through Risk with an atomic reservation; reduce-only/exit paths MUST use a safety validator and MUST NOT be blocked as new entries (G3.1).
- **FR-007**: System MUST implement kill-switch levels L1–L4 with durable persistence across restart; Telegram MAY trigger only L1 Pause (G3.2).
- **FR-008**: System MUST commit `order_intents` + `risk_reservations` + `audit_events` (and `notify_outbox` only if that step produces a notify event) in **one** durable transaction before `SUBMITTING`/network for every broker-bound submit; commit failure MUST abort send. On post-send uncertainty MUST mark UNKNOWN and reconcile without blind retry (G3.3, ADR-D03.1).
- **FR-009**: System MUST run Startup Recovery before READY and continuous reconciliation afterward, treating the broker as the source of truth for current exposure while preserving immutable intent/audit history. Missing data, auth/connect fail, incomplete pagination, or unresolved/stale breaks MUST keep the account locked / not READY, block exposure increases, and MUST NOT auto-lower KS; READY only after pagination complete, fresh data, and no unresolved breaks (G3.4, G3.6, §11.2).
- **FR-010**: System MUST provide a mandatory Telegram channel with durable outbox, event pushes, daily digest, Owner-only commands `/status` `/pnl` `/pause`, mode tagging on every message, and secret redaction. Inbound MUST persist/dedup `update_id`, reject wrong chat/user with audit, and reject commands older than **60s TTL**. Outbound MUST retry transient failures with bounded backoff and move permanent 4xx to dead-letter without deleting source journal events (G5.1–G5.5, ADR-D04).
- **FR-011**: System MUST enforce a single active account in D1a and keep LIVE hard-disabled until a separate Owner gate (G1.5, G2.4–G2.5).
- **FR-012**: System MUST run as one trading process with no localhost HTTP API surface in MVP (ADR-D13).
- **FR-013**: System MUST store secrets only in the OS secret store (keyring) and MUST redact secrets from journal, logs, UI surfaces, crash reports, and tests (ADR-D06, §18.3 #8).
- **FR-014**: System MUST provide automated evidence for unit/FSM tests, Strategy→Risk→OMS→Paper integration, and D1a rows of the fault matrix (§18), sufficient to fill capability-matrix Evidence cells for D1a exit.
- **FR-015**: System MUST normalize instrument/exposure projection for Paper so Risk sees consistent position/margin semantics (G1.4).

### Key Entities

- **Account**: Single active Paper account; mode tag PAPER; eligibility/ready flags; linked secret references (no plaintext).
- **Instrument (Paper)**: Synthetic internal id + Owner timeframe; not a D0-11 venue lock; no real-exchange hard-code in D1a.
- **Market Candle / Feature Snapshot**: Closed OHLCV and derived SMA/ATR features with schema version and event time.
- **Strategy Signal**: Entry/exit/abstain decision from `rule_sma_cross_v1` with parameters and rationale metadata.
- **Risk Check & Reservation**: Authorization to increase exposure; quantity/notional; lifecycle until release/consume after recon.
- **Order Intent**: Durable desired order with FSM state, client identity, linked reservation and risk-check id, protection spec.
- **Broker Order / Fill / Position**: Simulated broker truth for current exposure; fills idempotent by identity.
- **Kill-Switch State**: Persisted level L1–L4, scope, reason, latch across restart.
- **Audit Event**: Immutable record of safety-relevant actions and outcomes.
- **Notify Outbox Item**: Durable Telegram payload with dedup keys, retry/backoff state, dead-letter flag, mode/account tags.
- **Telegram Update Record**: Persisted `update_id` with accepted/rejected outcome for inbound dedup.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Two Paper replays with identical seed, config, and candle input produce bit-for-bit equal signal/order/fill/balance outcomes (G2.3).
- **SC-002**: 100% of scripted broker-bound submits in the D1a suite show one pre-SUBMITTING transaction containing intent + reservation + audit (and outbox iff a notify was produced); zero adapter calls occur when that commit fails or Risk rejects (G3.1, G3.3, §18.3 #1).
- **SC-003**: Across the certified D1a fault suite (crash, timeout, partial/late/duplicate fill, stale, disk, KS persist), duplicate exposure count is zero and UNKNOWN paths never blind-retry (G3.3, §18.3 #2–#3).
- **SC-004**: After every unclean-restart or incomplete-recovery script (missing data, auth fail, incomplete pagination), persisted KS level is not lower than before, the account does not reach READY, exposure increases remain blocked, and READY occurs only after full recovery success criteria (G3.6, §18.3 #4–#5).
- **SC-005**: After recon scripts that inject orphans/missed fills, ending current exposure matches the simulated broker, while intent/audit history remains intact (G3.4, §18.3 #7).
- **SC-006**: Deterministic tests for `rule_sma_cross_v1` cover crossover entry, exit, cooldown, ATR stop distance, abstain, and long-only behavior with zero look-ahead on open candles (G4.1, §07.3–§07.4).
- **SC-007**: Telegram suite shows successful Owner **test message** (G5.1); rejection+audit of wrong chat/user; `update_id` dedup; TTL **60s** rejection; outbox replay after restart; **delivery** transient retry then permanent-4xx dead-letter without source-event loss; command allowlist only `/status` `/pnl` `/pause`; mode tag on 100% of outbound messages; **daily digest** includes P&L, order counts, drawdown, KS, adapter health, and data-as-of time (G5.1–G5.5).
- **SC-008**: Secret/PIN/token scan of journal, config fixtures, logs, and test artifacts finds zero live credentials; only keyring references are stored (ADR-D06, §18.3 #8).
- **SC-009**: Capability matrix Evidence cells for D1a-required rows (G2.3, G3.1–G3.4, G3.6, G4.1, G5, ADR-D03.1, ADR-D13 invariants applicable at D1a, fault matrix D1a groups) are fillable from recorded reports (versions, seed/config, results).
- **SC-010**: Operational soak ≥14 days is explicitly **not** required to claim D1a exit; soak remains an operations proof for later DEMO/UI phases and never proves profitability (G2.3/G4.1 clarification).

## Out of Scope (D1a)

- Real CCXT / DEMO exchange trading and binding a real venue symbol/TF (D1b — only after mục 16 / D0-11 locks exchange/symbol)
- Hard-coding a real exchange or venue symbol into D1a as if D0-11 were complete
- Full PySide6 UI MVP and installer (D1c)
- LIVE trading and LIVE-native stop certification gate (D1.1)
- MT5, multi-account, external adapter plugins
- Backtest UI / deterministic backtest product (D3)
- AI/ML, vector stores, `ai_*` schema, model promote (D4)
- Localhost HTTP API between processes
- Committing real secrets, PIN values, bot tokens, or Chat IDs into the repository
- Using ≥14-day soak as a D1a exit gate or as proof of strategy profitability

## Assumptions

- Target user is a single Owner on Windows desktop (no SaaS / multi-tenant / app login).
- Feature scope is limited to **phase D1a**; later phases are named only as boundaries.
- Normative constraints come from `Kien-truc-App-Desktop-Solo-v1.4.md`; Enterprise docs are advisory only.
- One **synthetic internal** simulated symbol and one Owner-configured timeframe are sufficient until D0-11 unlocks D1b; do not treat mục 16 candidates (e.g. BTC/USDT) as locked for D1a.
- Paper fee/slippage defaults are Owner-configurable; exact default numbers may follow architecture examples if not overridden in mục 16.
- Paper fidelity limit (clarified): OHLC never implies book depth; partial-fill matrix rows are injection-driven.
- D1a may exercise kill-switch and Telegram without the full D1c desktop chrome; local activation hooks are acceptable for tests and attended operation.
- PIN verifier: ADR-D03.1 `pin_verifier` table MUST exist in D1a; Argon2id hash + lockout unit behavior is in D1a scope; full Settings/tray PIN UX waits for D1c.
- Daily Telegram digest uses the Owner’s local day boundary.
- “Broker” in D1a means the Fake/Paper simulated broker.
- D1a notify channel is Telegram outbox only (no toast UI chrome until D1c).
- OMS/order `UNKNOWN` forbids blind **order** retry; Telegram outbox may retry **delivery** only.
