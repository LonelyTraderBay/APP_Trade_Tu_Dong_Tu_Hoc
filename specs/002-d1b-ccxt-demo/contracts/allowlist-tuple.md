# Contract: Certified DEMO Allowlist Tuple

**Phase**: D1b  
**Normative**: v1.4 §05.3 allowlist; mục 16 D0-11; spec FR-001/002/009

## Locked tuple (immutable in D1b without architecture amend)

| Field | Value |
|---|---|
| `exchange_id` | `binance` |
| `market` | `spot` |
| `sandbox` | Binance Spot Testnet (DEMO) |
| `symbol` | `BTC/USDT` |
| `timeframe` | `15m` |
| `adapter_id` | `ccxt` |
| `mode` | `DEMO` only |

Canonical key: `binance|spot|binance_spot_testnet|BTC/USDT|15m`

## Behaviors

| Input | Required result |
|---|---|
| Exact tuple + valid cert + DEMO active | May become READY for trading |
| Any other `exchange_id` | Refuse before send; audit |
| `mode=LIVE` or production endpoint | Refuse; hard-disable |
| Symbol/TF ≠ locked | Refuse |
| Cert invalid / missing | Not READY; no place_order |
| Cert assumptions changed | Invalidate cert; refuse until re-cert |

## Negative tests (required)

- Second exchange config attempt
- LIVE enable attempt
- Wrong symbol (e.g. `ETH/USDT`)
- Wrong TF (e.g. `5m`)
- Production base URL / non-testnet sandbox flag
