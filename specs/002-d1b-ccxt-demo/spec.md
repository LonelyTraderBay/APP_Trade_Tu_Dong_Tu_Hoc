# Feature Specification: D1b CCXT DEMO Allowlist

**Feature Branch**: `002-d1b-ccxt-demo`

**Created**: 2026-07-23

**Status**: Ready for planning — clarified 2026-07-23; **implementation waits** until D1a PR #5 is merged to `main`

**Input**: User description: "Phase D1b: một CCXT DEMO allowlist đúng tuple đã chốt ở mục 16 (exchange + market + sandbox + symbol + TF). Contract/fault suite + ≥50 lifecycle + soak ≥72h. Không LIVE, không multi-exchange, không UI đầy đủ (D1c). Kế thừa D1a Paper core đã merge; không phá UNKNOWN/Risk/OMS invariants."

**Owner clarifications (2026-07-23)**: Q1=A, Q2=A, Q3=A

## Clarifications

### Session 2026-07-23

- Q: Operator surface without D1c UI → A: Headless/CLI + keyring + Telegram (`/status` `/pnl` `/pause`); no PySide6 Broker Hub in D1b
- Q: Definition of one completed DEMO lifecycle (for ≥50 gate) → A: Round-trip to flat — entry → fills → exit/flatten → flat with no UNKNOWN/open recon
- Q: Soak ≥72h continuous rules → A: Wall-clock 72h uninterrupted; no Owner pause; sleep/resume OK if recovery clean and zero unresolved recon
- Q: Paper vs DEMO concurrency → A: Exactly one active trading account at a time; CLI switch Paper↔DEMO; both profiles may exist; no concurrent trading
- Q: Evidence source for ≥50 lifecycles + soak → A: Both require real Binance Spot Testnet; contract/fault may use mock/inject separately and do not count toward the 50

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bind and trade only the certified DEMO tuple (Priority: P1)

As Owner, I configure credentials for exactly one certified DEMO exchange connection via headless/CLI (secrets in OS keyring; Test connection; enable/disable DEMO). The system connects in DEMO mode only, runs the existing rule strategy on that symbol/timeframe, and places/manages orders through the same Risk → durable intent → broker path proven in Paper. Telegram continues to expose `/status`, `/pnl`, and `/pause` with mode tagged DEMO. Any other exchange, market, live endpoint, or symbol is refused fail-closed. Full Broker Hub / Settings UI remains D1c.

**Why this priority**: Without a single certified DEMO path, D1b has no product value and risks accidental multi-venue or LIVE exposure.

**Independent Test**: With only the locked DEMO tuple configured, Owner can complete a full order lifecycle on DEMO; attempting a non-allowlisted venue/symbol/mode is rejected before any network order send.

**Acceptance Scenarios**:

1. **Given** mục 16 has locked the DEMO allowlist tuple (`binance` / spot / Binance Spot Testnet / `BTC/USDT` / `15m`) and Owner has stored DEMO credentials via headless/CLI into the OS secret store and passed Test connection, **When** Owner enables DEMO trading via CLI, **Then** the system becomes ready only for that exact exchange/market/sandbox/symbol/timeframe and refuses other combinations.
2. **Given** a ready DEMO session, **When** the strategy emits an entry signal on a closed candle for the locked symbol/timeframe, **Then** Risk reservation and durable intent are committed before any broker network send, and the order progresses through the same lifecycle states as Paper (including UNKNOWN → query/recon, never blind retry).
3. **Given** configuration that points at LIVE, a second exchange, or an uncertified symbol, **When** Owner attempts to enable trading, **Then** the system remains fail-closed (not READY for trading) and records a clear audit reason without sending orders.

---

### User Story 2 - Prove DEMO safety with contract, fault, and lifecycle evidence (Priority: P1)

As Owner, before trusting the DEMO adapter for continuous use, I require the same class of safety evidence as architecture gate D1b: contract checks for the certified tuple, injected fault scenarios (timeouts, UNKNOWN, disconnect, partial fill semantics as applicable), at least 50 completed order lifecycles on DEMO, and a continuous soak of at least 72 hours with no unresolved reconciliation.

**Why this priority**: Architecture exit criteria for D1b are evidence-based; connection alone is not enough.

**Independent Test**: Run the D1b evidence suite against the certified DEMO tuple and produce a pass record covering contract, fault matrix, ≥50 lifecycles, and ≥72h soak without unresolved recon.

**Acceptance Scenarios**:

1. **Given** the certified DEMO tuple, **When** the contract suite runs, **Then** required trading capabilities for that tuple pass and failures block “certified for DEMO trading” status.
2. **Given** injected faults equivalent to the architecture fault matrix (timeout after send, UNKNOWN, reconnect, credential/network loss), **When** the suite completes, **Then** invariants hold: no blind retry after UNKNOWN, Risk/intent durability preserved, broker remains source of truth for current exposure, local journal remains source of truth for intent/FSM/audit/outbox.
3. **Given** a DEMO evidence run on **real Binance Spot Testnet**, **When** at least 50 **completed lifecycles** finish — each = entry signal through entry fills, then exit/flatten to **flat**, with no remaining UNKNOWN or open reconciliation — **Then** the run is recorded as meeting the lifecycle gate (mock/injected contract-fault runs do not count toward the 50).
4. **Given** a continuous DEMO soak of at least 72 hours **wall-clock** on **real Binance Spot Testnet** with no Owner pause (Windows sleep/resume allowed only if recovery/recon completes cleanly), **When** the soak ends, **Then** there are zero unresolved reconciliation cases and no silent drift between broker exposure and local intent state.

---

### User Story 3 - Keep Paper and D1a invariants while DEMO is available (Priority: P2)

As Owner, I can still use Paper for deterministic local validation. Enabling DEMO does not remove the Paper profile, does not open LIVE, does not add a second exchange, and does not require the full desktop UI surface planned for D1c. Exactly one trading account is active at a time: Owner switches Paper ↔ DEMO via CLI. Operator surface for D1b is headless/CLI + keyring + existing Telegram commands only; Broker Hub / Settings completeness stays out of scope until D1c.

**Why this priority**: Protects the merged D1a core and keeps phase boundaries clear.

**Independent Test**: With DEMO code present, Paper still passes its D1a regression suite; LIVE remains hard-disabled; only one certified DEMO venue can be active.

**Acceptance Scenarios**:

1. **Given** D1a Paper core merged to `main` as the baseline, **When** D1b DEMO support is added, **Then** Paper regression (Risk before network, UNKNOWN handling, recovery, Telegram outbox commands already delivered) still passes, and Owner can switch the single active account between Paper and DEMO via CLI without concurrent trading.
2. **Given** DEMO is the active account, **When** Owner looks for LIVE trading, a second exchange, or a second simultaneous active account, **Then** those paths remain unavailable / hard-disabled for this phase.
3. **Given** attended-only baseline, **When** the process is not under Owner attendance rules for DEMO, **Then** the system does not assume unattended LIVE-class operation (no expansion of attendance model beyond architecture baseline).
4. **Given** open intents or non-flat exposure on the active account, **When** Owner requests a Paper↔DEMO switch, **Then** the switch is refused until flat and no open recon (fail-closed).

---

### Edge Cases

- Sandbox/demo endpoint unavailable or returns capability mismatch → fail-closed, not READY; no order send.
- Credential missing, invalid, or wrong environment (LIVE key used against DEMO expectation) → reject before trading READY.
- Timeout or ambiguous response after order send → mark UNKNOWN; query/recon only; never blind resend with a new client identity.
- Broker reports exposure that disagrees with local open intents → recon path; unresolved recon blocks new risk-increasing orders.
- Symbol/timeframe drift vs locked tuple (renamed market, wrong TF feed) → refuse trading until tuple re-certified.
- Process crash mid-DEMO order → startup recovery restores durable intents without duplicate exposure (same invariant as Paper).
- Attempt to activate Paper and DEMO trading concurrently, or switch account while non-flat / open recon → refused fail-closed.
- Entry-only fills, cancels-before-send, intents left UNKNOWN/open-recon, or lifecycles from mock/injected (non-real-testnet) runs MUST NOT count toward the ≥50 completed-lifecycle gate.
- Soak interrupted by Owner pause → soak **fails** continuous gate (must restart wall-clock window); Windows sleep/resume does not fail the gate if recovery subset + recon complete with zero unresolved cases before new risk-increasing orders.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow DEMO trading only for the single allowlist tuple locked in architecture mục 16:
  - exchange id: `binance`
  - market: spot
  - sandbox: Binance Spot Testnet (DEMO only; not LIVE)
  - symbol: `BTC/USDT`
  - timeframe: `15m`
- **FR-002**: System MUST refuse LIVE mode, multi-exchange trading, and any venue/symbol/mode outside that certified DEMO tuple (fail-closed, no order send).
- **FR-003**: System MUST reuse D1a Risk → durable intent commit → broker send ordering for every exposure-increasing DEMO action; broker is truth for current exposure; local store is truth for intent/FSM/audit/outbox.
- **FR-004**: System MUST treat UNKNOWN / timeout-after-send on DEMO with query/recon only; MUST NOT blind-retry a new send for the same intent.
- **FR-005**: System MUST keep the Paper profile available and MUST NOT regress D1a Paper safety behaviors when DEMO is introduced. Exactly one trading account MUST be active at a time; Owner MAY switch Paper ↔ DEMO via CLI only when flat with no open reconciliation; concurrent Paper+DEMO trading MUST be refused.
- **FR-006**: System MUST bind the default D1 strategy `rule_sma_cross_v1` to `BTC/USDT` @ `15m` on DEMO, using closed candles only and a declared feature schema version.
- **FR-007**: System MUST store DEMO API secrets only in the OS secret store; logs, UI surfaces, and local DB MUST redact secrets and sensitive identifiers.
- **FR-008**: System MUST provide a certification/evidence gate for the locked tuple covering: contract capability checks, fault-injection scenarios aligned with architecture mục 18, ≥50 **completed DEMO lifecycles** on **real Binance Spot Testnet** (each = entry through exit/flatten to flat with no UNKNOWN or open recon), and continuous DEMO soak ≥72 hours **wall-clock** on that same real testnet with no Owner pause, zero unresolved reconciliation at end (sleep/resume allowed only with clean recovery/recon). Contract/fault suites MAY use mocks/injection and MUST NOT count toward the ≥50 lifecycle total.
- **FR-009**: System MUST invalidate or refuse trading if certification assumptions change (endpoint, market type, credential scope, instrument metadata) until the tuple is re-certified.
- **FR-010**: System MUST NOT deliver full D1c UI (Broker Hub/Settings completeness, installer polish). D1b operator surface MUST be headless/CLI for credential store (keyring), Test connection, and DEMO enable/disable, plus Telegram `/status` `/pnl` `/pause` with mode DEMO; MUST NOT require a PySide6 Broker Hub stub.
- **FR-011**: System MUST remain a single trading process with no localhost HTTP trading API in this phase.
- **FR-012**: Implementation baseline MUST be D1a Paper core **after PR #5 is merged to `main`**; D1b feature branch MUST then rebase/branch from that `main` before DEMO trading code lands. Spec/plan/tasks may proceed now; `/speckit-implement` MUST wait for that merge.

### Key Entities

- **Certified DEMO Allowlist Tuple**: Locked combination — `binance` + spot + Binance Spot Testnet + `BTC/USDT` + `15m` — that alone may trade in D1b.
- **DEMO Connection Profile**: Owner-configured DEMO credentials and connection status for that tuple (secrets by reference only).
- **Order Intent / Lifecycle**: Durable local record of intended orders and FSM states shared with D1a semantics. A **completed DEMO lifecycle** (evidence unit) is a round-trip: entry → fills → exit/flatten → flat, with no UNKNOWN or open reconciliation remaining.
- **Reconciliation Case**: Discrepancy between broker exposure and local intents; must reach resolved or block risk-increasing activity.
- **Certification Evidence Record**: Pass/fail artifacts for contract, fault, lifecycle count, and soak duration for the locked tuple. Lifecycle (≥50) and soak (≥72h) evidence MUST come from real Binance Spot Testnet; contract/fault may be separate mock/inject runs.
- **Paper Session**: Existing simulated venue retained for deterministic validation alongside DEMO; selectable as the sole active account via CLI switch, never concurrent with DEMO trading.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Owner can enable trading on exactly one locked DEMO venue/symbol/timeframe (`binance` spot testnet `BTC/USDT` `15m`) and cannot enable a second venue or LIVE in this phase (100% refusal in acceptance checks).
- **SC-002**: Every risk-increasing DEMO order attempt shows durable intent recorded before broker send in audit/evidence review (0 violations in the D1b safety suite).
- **SC-003**: After simulated or real DEMO ambiguous send outcomes, 100% of cases use query/recon rather than blind resend (0 blind retries in fault evidence).
- **SC-004**: Evidence pack shows at least 50 completed DEMO lifecycles on real Binance Spot Testnet for the locked tuple, each round-trip to flat with no UNKNOWN/open recon (mock/fault runs excluded from the count).
- **SC-005**: Evidence pack shows continuous DEMO operation of at least 72 hours wall-clock on real Binance Spot Testnet without Owner pause, ending with zero unresolved reconciliation cases (sleep/resume only if recovery/recon stayed clean).
- **SC-006**: D1a Paper regression suite remains fully passing after DEMO support is added.
- **SC-007**: Attempts to trade with missing/invalid DEMO credentials, wrong environment, or non-allowlisted symbol fail closed before any order is sent (demonstrated in acceptance tests).

## Assumptions

- Target user is a single Owner on Windows desktop (no SaaS / multi-tenant / app login).
- Feature scope is limited to phase **D1b**; out of scope: LIVE (D1.1), second exchange/multi-account (D2), full PySide6 MVP UI/installer (D1c), backtest UI (D3), AI/ML (D4).
- Normative constraints come from `Kien-truc-App-Desktop-Solo-v1.4.md` (especially D1b row in phase plan, allowlist/certification, mục 18 faults, D0-11); Enterprise docs are advisory only.
- Strategy remains `rule_sma_cross_v1` with Owner-accepted defaults from mục 16 (spot long-only, default guardrails).
- D0-06 (ToS review for Binance Spot Testnet / bot use) remains an Owner gate before DEMO credentials are used for real-network certification — not a code deliverable.
- D1a baseline = **merged** PR #5 on `main` (Owner choice Q3=A). Until then: clarify/plan/tasks OK; implement blocked.
- Attended-only baseline from architecture remains; D1b does not expand to unattended LIVE-class operation.
- No secrets (API keys, tokens, chat IDs) are written into repo or mục 16 text.
- ≥50 lifecycle + ≥72h soak gates use real testnet only; simulated/fault-injected runs are for contract/fault evidence, not lifecycle count.

## Out of Scope

- LIVE trading enablement or LIVE hard-disable removal
- Multi-exchange, multi-account, MT5
- Full desktop UI (D1c): Broker Hub completeness, Settings completeness, installer, credential wizard UI
- Backtest/replay product surface (D3) and AI module (D4)
- Changing D1a UNKNOWN / Risk / OMS invariants
- Starting DEMO trading implementation before D1a is on `main`
