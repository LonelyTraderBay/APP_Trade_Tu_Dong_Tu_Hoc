# Contract: Broker Adapter Interface (D1a — Paper/Fake)

**Phase**: D1a  
**Normative**: v1.4 §05 / ADR-D09 (interface spine); G2.3 Paper fidelity  
**Implementations in D1a**: `PaperAdapter` / `FakeBroker` only

## Purpose

Define the port OMS/ledger/recovery call so Strategy/Risk/OMS never depend on venue SDKs. Contract tests bind this surface for Paper; D1b will add a CCXT implementation against the **same** port after D0-11.

## Identity & manifest (minimum)

| Field | D1a expectation |
|---|---|
| `adapter_id` | `paper` |
| `modes` | `PAPER` only |
| `capabilities` | place, cancel, query_by_client_id, list_open_orders (paginated), list_executions (cursor+overlap), positions, balances, protective orders (simulated) |
| `instrument_model` | Normalized internal symbol; tick/lot; **no** real venue required |

## Required operations

| Operation | Semantics |
|---|---|
| `connect()` / `disconnect()` | Local sim; auth fail injectable for recovery tests |
| `get_capabilities()` / clock skew probe | Support ADR-D12 freshness gates |
| `place_order(client_order_id, …)` | Idempotent on client_order_id; happy path **full fill** (+ fee/slippage config) |
| `cancel_order(…)` | May race with late fill (fault injectable) |
| `query_order_by_client_id(…)` | Mandatory for UNKNOWN recovery |
| `list_open_orders(page…)` | Pagination must complete before READY |
| `list_executions(cursor, overlap)` | Dedup-friendly; overlap required |
| `get_positions()` / `get_balances()` | Current exposure SoT for Paper |
| `upsert_protection(…)` | Simulated stop attach/update; failure → KS/flatten path in core |

## Fault injection hooks (test-only)

- Crash markers around send boundary
- Timeout after “transmission started”
- Partial/late/duplicate fills (**injection only**; never from OHLC inference)
- Stale quote / disconnect / disk-pressure coordination via test doubles

## Non-goals (D1a)

- Real network / CCXT
- LIVE mode
- Inferring liquidity from OHLC

## Contract test obligations

See `tests/contract/` — must cover precision, place/status/cancel, direct fill, injected partial/late, client-ID lookup, fee, pagination, protection update failure.
