# Contract: CCXT DEMO Adapter (Binance Spot Testnet)

**Phase**: D1b  
**Normative**: v1.4 §05 / ADR-D09; extends D1a [broker-adapter.md](../../001-d1a-paper-core/contracts/broker-adapter.md)  
**Implementation**: `src/autotrade/core/adapters/ccxt_demo/` only

## Purpose

Provide a Broker Adapter Interface implementation for **one** certified DEMO tuple. Same OMS/ledger/recovery call surface as Paper; network I/O confined here.

## Manifest (minimum)

| Field | D1b expectation |
|---|---|
| `adapter_id` | `ccxt` |
| `exchange_id` | `binance` (allowlist-enforced) |
| `modes` | `DEMO` declared; `LIVE` not certifiable in D1b |
| `markets` | `spot` |
| `capabilities` | place, cancel, query_by_client_id, list_open_orders (paginated), list_executions (cursor+overlap), positions, balances, OHLCV closed candles; protection per capability snapshot |
| `sandbox` | Binance Spot Testnet only |

## Required operations

Same as D1a broker port:

| Operation | DEMO notes |
|---|---|
| `connect` / `disconnect` | Load keyring secrets; verify testnet; refuse LIVE hosts |
| `get_capabilities` / clock probe | Freshness gates (ADR-D12) |
| `fetch_ohlcv` / candle ingest hook | Closed `BTC/USDT` `15m` only for strategy path |
| `place_order(client_order_id, …)` | Idempotent on client id where exchange supports; spot long-only D1 |
| `cancel_order` | Race with late fill handled via recon |
| `query_order_by_client_id` | **Mandatory** for UNKNOWN |
| `list_open_orders` / `list_executions` | Pagination/cursor+overlap before READY |
| `get_positions` / `get_balances` | Broker SoT for DEMO exposure |
| `upsert_protection` | Best-effort per capability; failure → core KS/flatten policy |

## Sandbox guard

- Trading calls MUST target Binance Spot Testnet configuration only.
- Detecting production endpoints or LIVE account mode → fail-closed, no send.
- Credential env mismatch (e.g. key marked live) → reject READY.

## Fault injection (test double / hooks)

- Timeout after transmission started → UNKNOWN path
- Disconnect / rate-limit
- Duplicate / out-of-order executions
- Partial/late fills (when supported or injected)
- Auth failure

These runs **do not** count toward ≥50 real lifecycles.

## Non-goals

- Multi-exchange CCXT trading
- LIVE trading
- Import of `ccxt` from Strategy/Risk/OMS
- Full UI wizard (D1c)

## Contract test obligations

`tests/contract/` must cover: allowlist bind, precision, place/status/cancel, client-ID lookup, pagination/cursor, fee mapping, sandbox refusal, capability mismatch fail-closed. Real network optional under `AUTOTRADE_D1B_REAL=1`.
