# Data Model: MVP D1a Paper Core

**Normative**: ADR-D03.1 (v1.4). Column types finalized in Alembic; this doc locks **tables, roles, and invariants** required before D1a exit. **No `ai_*` tables.**

## Entity overview

```text
Account ──┬── AccountSecretsRef (keyring pointers only)
          ├── InstrumentCache (synthetic internal symbol)
          ├── StrategyBinding (rule_sma_cross_v1 + TF)
          ├── KillSwitchState
          ├── ExecutionCursor
          ├── RiskCheck ── RiskReservation ── OrderIntent ── Order ── Fill
          │                                      └── OrderProtection
          ├── PositionLocal (derived; not exposure SoT)
          ├── BalanceSnapshot
          ├── ReconBreak
          ├── MarketCandle → FeatureSnapshot → Signal
          ├── AuditEvent
          └── NotifyOutbox
TelegramUpdate (global dedup by update_id)
AppSettings / PinVerifier / SchemaMeta
```

## Tables (ADR-D03.1)

| Table | Purpose | Core fields / constraints |
|---|---|---|
| `schema_meta` | Migration/app version | alembic_version (or equiv.) |
| `app_settings` | Non-secret config | key/value; **no** secret plaintext |
| `pin_verifier` | PIN Argon2id | salt, hash, failed_count, lockout_until |
| `accounts` | Logic account | account_id, adapter_id=`paper`, mode=`PAPER`, endpoint, external_id, status, eligibility |
| `account_secrets_ref` | Keyring refs | account_id, keyring_service, keyring_user |
| `instruments_cache` | Normalized instrument | **internal_symbol** (e.g. `PAPER-INTERNAL-1`), venue_refs nullable/empty in D1a, tick/lot, updated_at, ttl |
| `strategy_bindings` | Strategy↔account | strategy_id=`rule_sma_cross_v1`, account_id, symbol, timeframe, params_json, enabled |
| `market_candles` | Confirmed OHLCV | symbol, timeframe, open_time, OHLCV, `is_closed`; UNIQUE(symbol,timeframe,open_time) |
| `feature_snapshots` | Versioned features | feature_schema_version, event_time, symbol, payload_ref/hash; closed candle only |
| `signals` | Strategy outputs | signal_id, strategy_id, event_time, side, strength, feature_snapshot_id |
| `risk_checks` | Risk results | risk_check_id, account_id, result, reasons_json, at |
| `risk_reservations` | Atomic reservation | reservation_id, account_id, intent_id, qty/notional, state, at |
| `order_intents` | Pre-network intent | intent_id, client_order_id, FSM state, protection spec, risk_check_id, reservation_id |
| `orders` | Local↔broker map | broker_order_id nullable, delivery_certainty, state, intent_id |
| `order_protection` | Stop/contingent | protection_id, links intent/order/leg, qty, status |
| `fills` | Immutable fills | UNIQUE(account_id, broker_execution_id); qty, price, fee, ts |
| `positions_local` | Derived view | legs/tickets + provenance; **not** current exposure SoT |
| `balances_snapshots` | Account snapshots | equity/margin/ts/source |
| `recon_breaks` | Recon gaps | type, payload, status, at |
| `kill_switch_state` | KS persist | scope, level, triggers_json, latched |
| `execution_cursors` | Ingest cursor | account_id, cursor, overlap_policy |
| `audit_events` | Immutable audit | event_id, type, payload_redacted, at, correlation_id |
| `notify_outbox` | Notify queue | event_id, channel, status, attempts, next_attempt, dead_letter |
| `telegram_updates` | Inbound dedup | update_id UNIQUE, accepted/rejected |

## Order intent FSM (local)

States per v1.4 §11 (subset exercised in D1a Paper):

`CREATED` → `RISK_REJECTED` | `RESERVED` → `SUBMITTING` → `ACKNOWLEDGED` | `FILLED` | `REJECTED` | `UNKNOWN` → (via recon) terminal broker-aligned states; cancel path includes `CANCEL_REQUESTED` / `CANCEL_UNKNOWN`.

**Delivery certainty** (separate axis): `NOT_SENT` → `SENDING` → `CONFIRMED` | `MAY_HAVE_BEEN_ACCEPTED`.

## Reservation states

Typical: `HELD` → `CONSUMED` | `RELEASED` (only after recon proves no exposure / terminal reject). UNKNOWN **must not** release early.

## Kill-switch

Levels L1–L4 persisted; restart MUST NOT auto-lower. Telegram may set L1 only.

## Validation rules

- Money/qty: `Decimal` (or integer minor units) — never binary float for risk math.
- Candles used for signals: `is_closed=true` only.
- Feature rows require `feature_schema_version`.
- Fills idempotent on `(account_id, broker_execution_id)`.
- Pre-SUBMITTING txn MUST include intent + reservation + audit (+ outbox iff event).
- Secrets never stored in `app_settings` or audit payloads (redacted).
- Instrument `internal_symbol` MUST NOT be treated as a certified venue symbol.

## Truth boundaries

| Concern | Source of truth |
|---|---|
| Current exposure / open orders / balances (live view) | Paper/Fake **broker** |
| Intent, FSM, reservations, audit, outbox, ingested fills | **SQLite** |
| Diagnostics | JSONL (non-authoritative) |
