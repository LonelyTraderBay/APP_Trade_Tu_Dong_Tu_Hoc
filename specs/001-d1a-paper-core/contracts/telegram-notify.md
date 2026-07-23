# Contract: Telegram Notify Channel (D1a)

**Phase**: D1a  
**Normative**: v1.4 §08, G5.1–G5.5, ADR-D04/D10  
**Clarification**: Q4

## Configuration (runtime, not repo)

- Bot token via **keyring** only
- Exactly one private Chat ID + Owner User ID in non-secret settings / refs
- Message language default: Vietnamese; mode tag required on every outbound message

## Inbound

| Rule | Behavior |
|---|---|
| Dedup | Persist every `update_id` in `telegram_updates` (accepted or rejected) |
| Actor | Accept only configured private chat + Owner user ID; else reject + audit |
| Allowlist | `/status`, `/pnl`, `/pause` only (`/pause` → L1 only) |
| TTL | Reject commands older than **60s**; audit |
| Forbidden | Remote resume / flatten / unlock; PIN/credentials via chat |

## Outbound / outbox

| Rule | Behavior |
|---|---|
| Durability | Insert `notify_outbox` as durable record; `asyncio.Queue` wake-only |
| Retry | Transient errors (incl. 429): bounded backoff + `next_attempt` |
| Dead-letter | Permanent 4xx → `dead_letter=true`; surface unhealthy; **do not** delete source journal/audit events |
| Restart | Replay pending outbox rows |
| Content | Include `mode` (PAPER) + account; redact secrets |

## Events (minimum D1a)

Bot start/stop; adapter connect OK/FAIL; fill/reject; risk reject; KS change; recon break; recovery fail/SAFE_LOCK; disk/DB/outbox unhealthy; feed stale; daily digest (P&L, orders, drawdown, KS, adapter health, as-of time).

## Test obligations

- Wrong chat/user rejected
- `update_id` replay ignored
- TTL expiry rejected
- Outbox survives process restart
- Transient then dead-letter path without source-event loss
- Redaction scan on payloads
