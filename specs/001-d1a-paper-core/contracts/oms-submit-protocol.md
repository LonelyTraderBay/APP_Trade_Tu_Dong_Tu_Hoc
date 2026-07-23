# Contract: Durable OMS Submit Protocol (D1a)

**Phase**: D1a  
**Normative**: v1.4 §11.1–11.3; G3.3; ADR-D03.1 commit rule  
**Clarifications**: Q2 (atomic bundle), Q3 (recovery lock)

## Pre-SUBMITTING transaction (mandatory)

In **one** SQLite transaction, before any adapter call:

1. Create/update `order_intents` with deterministic `client_order_id`, protection spec, links
2. Persist `risk_checks` result and `risk_reservations` row (state HELD)
3. Append `audit_events` (redacted payload)
4. Insert `notify_outbox` **only if** this step emits a notify event
5. Intent local state = `RESERVED`

**Commit success** → transition to `SUBMITTING`, set delivery `SENDING`, call adapter.  
**Commit failure** → no adapter call; SAFE_LOCK / fail-closed as ADR-D03.

## Post-send outcomes

| Outcome | Order / delivery | Reservation | Next action |
|---|---|---|---|
| Ack / fill / reject observed | Persist idempotently | Consume/release per rules | Audit + outbox |
| Timeout after possible transmission | `UNKNOWN` + `MAY_HAVE_BEEN_ACCEPTED` | **Hold** | Query by client ID + executions/open orders; **no blind retry** |
| Crash after commit before/during send | Recovery classifies NOT_SENT vs uncertain | Hold if uncertain | Same as UNKNOWN path |

## Startup Recovery gate (before READY)

Follow §11.2 steps 1–10 for the Paper account. If missing data, auth/connect fail, pagination incomplete, or unresolved breaks → account remains **not READY**; KS not auto-lowered; exposure increases blocked; Recovery SEV1 via outbox.

## Continuous recon

While open orders/positions exist: interval + on reconnect/cancel/flatten/clock jump; execution cursor with overlap + fill dedup. Broker wins current exposure; never blind-delete intent/audit history.

## Invariants (§18.3 applicable)

1–5, 7–8 must hold in fault suite. (#6 LIVE protection is D1.1 — not exercised as LIVE here, but Paper protection-failure paths still lock/flatten per matrix rows that apply.)

## Test mapping

- unit: FSM transitions, CAS/monotonic guards
- integration: Strategy→Risk→txn→OMS→Paper→ledger
- fault: §18.2 crash/timeout/partial/cancel-late/dup/stale/disk/KS restart/orphan
