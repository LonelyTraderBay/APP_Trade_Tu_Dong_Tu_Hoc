# Data Model: D1b CCXT DEMO Allowlist

**Normative**: ADR-D03.1 (unchanged core tables) + additive D1b certification/allowlist fields.  
**Baseline**: D1a schema from `specs/001-d1a-paper-core/data-model.md`. **No `ai_*` tables.**

## Entity overview (delta)

```text
Account (PAPER | DEMO)
  ├── is_active (exactly one true globally)
  ├── adapter_id: paper | ccxt
  ├── mode: PAPER | DEMO   (LIVE forbidden in D1b)
  ├── endpoint fingerprint (DEMO testnet class)
  ├── AccountSecretsRef (keyring) — DEMO API key/secret refs
  └── CertificationRecord? (required before DEMO READY)

AllowlistTuple (config constant / app_settings)
  binance + spot + Binance Spot Testnet + BTC/USDT + 15m

InstrumentCache
  internal_symbol + venue_symbol BTC/USDT for DEMO account
  precision/tick/lot from capability snapshot

StrategyBinding
  rule_sma_cross_v1 @ BTC/USDT 15m when DEMO active
  (Paper may keep PAPER-INTERNAL-1 binding on Paper account)

LifecycleEvidenceEvent (optional table or append-only evidence file)
  counts completed round-trips for ≥50 gate

SoakRun (optional) — start/end wall-clock, pause_flag, unresolved_recon_count
```

## Additive / extended tables

| Table / change | Purpose | Rules |
|---|---|---|
| `accounts` (+cols) | `is_active` BOOL; DEMO rows use `adapter_id=ccxt`, `mode=DEMO`, sandbox endpoint id | CHECK mode IN (`PAPER`,`DEMO`); LIVE insert rejected; ≤1 `is_active=1` |
| `account_secrets_ref` | DEMO keyring pointers | No plaintext secrets; separate from any future LIVE account |
| `instruments_cache` | Cache `BTC/USDT` metadata for DEMO | TTL/freshness; drift vs cert metadata hash → refuse READY |
| `strategy_bindings` | Bind strategy to active account symbol/TF | DEMO: `BTC/USDT` + `15m` + `rule_sma_cross_v1` |
| `certification_records` **NEW** | Tuple certification | See fields below; invalidation clears `valid` |
| `allowlist_config` **NEW** or `app_settings` keys | Locked tuple constants | Must match mục 16; not Owner-editable to other exchanges in D1b |
| `lifecycle_evidence` **NEW** (optional) | Count real completed round-trips | `source=real_testnet` only; mock rows excluded |
| `soak_runs` **NEW** (optional) | Soak window metadata | Owner pause → mark failed continuous gate |

### `certification_records` (minimum fields)

| Field | Notes |
|---|---|
| `cert_id` | PK |
| `tuple_key` | Canonical string e.g. `binance|spot|binance_spot_testnet|BTC/USDT|15m` |
| `app_version` / `ccxt_version` | Pin evidence |
| `endpoint_fingerprint` | Hash/class of sandbox base URLs used |
| `instrument_metadata_hash` | Precision/filters snapshot |
| `capability_snapshot_json` | Redacted capability result |
| `contract_suite_passed_at` | Timestamp |
| `fault_suite_passed_at` | Timestamp |
| `lifecycle_count` / `lifecycle_passed_at` | Real testnet ≥50 |
| `soak_started_at` / `soak_ended_at` / `soak_passed` | Real testnet ≥72h |
| `valid` | BOOL; false on invalidation |
| `invalidated_reason` | Nullable |

## Unchanged (must not regress)

All D1a ADR-D03.1 trading tables: intents, reservations, orders, fills, positions_local, recon_breaks, kill_switch_state, execution_cursors, audit_events, notify_outbox, telegram_updates, feature_snapshots, signals, market_candles, pin_verifier, schema_meta.

## Order intent FSM

Same as D1a §11. DEMO uses identical durable submit + UNKNOWN semantics. Delivery certainty axis unchanged.

## Completed DEMO lifecycle (evidence entity — conceptual)

```text
OPEN:  entry intent → RESERVED → SUBMITTING → … → position non-flat
CLOSE: exit/flatten intents → … → position flat
DONE:  no UNKNOWN intents; no open recon_breaks for account
```

Only `DONE` events with `source=real_testnet` increment lifecycle_count toward 50.

## Account switch state machine

```text
ACTIVE(Paper) --[flat & no open recon & no UNKNOWN]--> ACTIVE(DEMO)
ACTIVE(DEMO)  --[flat & no open recon & no UNKNOWN]--> ACTIVE(Paper)
any non-flat / open recon / UNKNOWN --> switch REJECTED (audit)
```

## Validation rules

- Money/qty: `Decimal` — never binary float for risk math.
- Candles for signals: `is_closed=true` only; DEMO symbol `BTC/USDT`, TF `15m`.
- Feature rows require `feature_schema_version`.
- Fills idempotent on `(account_id, broker_execution_id)`.
- Pre-SUBMITTING txn MUST include intent + reservation + audit (+ outbox iff event) **before** CCXT send.
- Secrets never in SQLite/audit plaintext.
- Allowlist mismatch → no network place_order.
- LIVE mode / production endpoint → fail-closed.
- Concurrent two `is_active` accounts → schema or app invariant violation (fail-closed).

## Truth boundaries

| Concern | Source of truth |
|---|---|
| Current exposure / open orders / balances (DEMO) | Binance Spot Testnet via CCXT adapter |
| Current exposure (Paper) | Paper adapter |
| Intent, FSM, reservations, audit, outbox, ingested fills | SQLite |
| Whether DEMO may trade | `certification_records.valid` + allowlist + active account |
| Diagnostics | JSONL (non-authoritative) |

## Migration note

- Alembic revision after D1a `0001_adr_d03_1_*` (e.g. `0002_d1b_certify_allowlist`).
- Migration MUST be fail-closed on error (ADR-D03).
- No `ai_*` tables.
