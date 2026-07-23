# Contract: Single Active Account Switch (Paper ↔ DEMO)

**Phase**: D1b  
**Normative**: v1.4 G1.5; spec FR-005; clarify Q4=A

## Invariant

At most **one** account has `is_active=true`. Active account is the only one that may increase exposure or send broker orders.

## Switch preconditions (all required)

1. Current active account is **flat** (no open position exposure per broker SoT).
2. No open `recon_breaks` in unresolved state.
3. No intents in `UNKNOWN` / `SUBMITTING` / non-terminal risk-increasing states.
4. Target account exists and is `PAPER` or certified `DEMO` (not LIVE).
5. For target DEMO: `certification_records.valid=true` for locked tuple.

## Results

| Case | Result |
|---|---|
| Preconditions OK | Deactivate source; activate target; audit event; Telegram mode follows new active |
| Any precondition fail | No change; audit reason; CLI non-zero exit |
| Concurrent activate attempt | Fail-closed |

## Tests

- Happy switch Paper→DEMO and DEMO→Paper when flat
- Refuse switch with open position
- Refuse switch with open recon or UNKNOWN
- Refuse activating second account without deactivating first
