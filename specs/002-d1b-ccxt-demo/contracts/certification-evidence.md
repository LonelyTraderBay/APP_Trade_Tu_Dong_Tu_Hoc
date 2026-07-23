# Contract: Certification & Evidence Gates

**Phase**: D1b  
**Normative**: v1.4 §05.5, §14 D1b exit; spec FR-008, SC-004/005; clarify Q2/Q3/Q5

## Certification sequence

1. Implement adapter + manifest; pin `ccxt`/app versions.  
2. **Contract suite** pass for locked tuple (mock OK).  
3. **Fault suite** pass (inject OK).  
4. **Real testnet**: ≥50 completed round-trip lifecycles.  
5. **Real testnet**: ≥72h wall-clock soak, no Owner pause, 0 unresolved recon at end.  
6. Persist `certification_records.valid=true` only when 2–5 recorded.  
7. DEMO trading READY may require valid cert (product rule: enable gated by cert).

LIVE certification is **out of scope** (does not inherit from DEMO).

## Lifecycle unit (counts to 50)

Round-trip on **real Binance Spot Testnet**:

`entry → fills → exit/flatten → flat` + no UNKNOWN + no open recon.

Excluded: mock/fault, entry-only, cancel-before-send, unresolved paths.

## Soak unit (72h)

- Wall-clock continuous process window ≥72h  
- Owner pause → fail continuous gate (restart required)  
- Sleep/resume OK iff recovery+recon clean before new risk-increasing orders  
- End state: 0 unresolved recon; no silent broker/local drift

## Evidence pack (minimum artifacts)

| Artifact | Content |
|---|---|
| Versions | app, Python, `ccxt`, lockfile hash |
| Tuple | canonical allowlist key |
| Contract/fault reports | pytest junit/log paths |
| Lifecycle log | ≥50 DONE events with timestamps/order ids (redacted) |
| Soak log | start/end UTC, pause=false, recon summary |
| Matrix update | `docs/mvp-capability-matrix.md` G1 / ADR-D09 / D1b exit cells |

## Invalidation

Any of: `ccxt` major bump, endpoint fingerprint change, credential scope change, instrument metadata hash change, allowlist amend → `valid=false` until suites re-run (lifecycle/soak re-run if semantics/endpoint changed).
