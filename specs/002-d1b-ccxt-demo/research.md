# Research: D1b CCXT DEMO Allowlist

**Feature**: `002-d1b-ccxt-demo` | **Date**: 2026-07-23  
**Sources**: v1.4 §§05, 06, 11, 14, 16, 18; AGENTS.md; spec + clarify session 2026-07-23; D1a plan/contracts

## R1 — Implementation baseline

- **Decision**: Spec/plan/tasks on branch `002-d1b-ccxt-demo` now; **no DEMO trading code merge** until PR #5 (D1a) is on `main`, then rebase this branch.
- **Rationale**: Spec FR-012 / Owner Q3=A; avoid dual-source drift with unmerged D1a.
- **Alternatives considered**: Implement atop unmerged D1a branch (rejected — Owner A); cherry-pick piecemeal (rejected — higher rebase risk).

## R2 — Dependency: CCXT only (no UI/ML)

- **Decision**: Add pinned `ccxt` to project deps + hashed lockfile; keep D1a stack; still ban PySide6/ML/vec/FAISS/MT5/FastAPI.
- **Rationale**: D1b exit requires real DEMO via CCXT family (v1.4 §05 group B); UI is D1c.
- **Alternatives considered**: Raw REST client (rejected — more solo maintenance); add PySide6 stub wizard (rejected — clarify Q1=A / FR-010).

## R3 — Adapter placement & isolation

- **Decision**: New package `src/autotrade/core/adapters/ccxt_demo/` implementing existing Broker Adapter Interface; `adapter_id=ccxt`, `exchange_id=binance` only via allowlist/cert config — **never** inside Strategy/Risk/OMS.
- **Rationale**: G1.1, ADR-D09, constitution V; D1a contract already anticipated CCXT on same port.
- **Alternatives considered**: Generic multi-exchange CCXT factory enabled for all `ccxt.exchanges` (rejected — G1.3 / allowlist); Binance-specific types in OMS (rejected).

## R4 — Sandbox / LIVE refusal

- **Decision**: Explicit sandbox guard binds Binance **Spot Testnet** DEMO endpoints/mode; trading READY requires `mode=DEMO` and testnet host class; production/`LIVE` endpoints and LIVE mode hard-fail before send.
- **Rationale**: G2.2/G2.4, FR-002, FR-001 tuple lock.
- **Alternatives considered**: Rely on Owner discipline only (rejected — fail-closed); allow “paper + live market data read-only” as D1b trading substitute (rejected — Owner chose real testnet evidence).

## R5 — Single active account switch

- **Decision**: Persist exactly one active account; CLI `switch paper|demo` only when flat, no open recon, no UNKNOWN; concurrent trading refused.
- **Rationale**: G1.5 + clarify Q4=A.
- **Alternatives considered**: Concurrent Paper+DEMO (rejected — G1.5); disable Paper entirely in D1b (rejected — FR-005 / SC-006).

## R6 — Certification record & invalidation

- **Decision**: Durable certification row/artifact for the locked tuple (versions: app, ccxt, endpoint fingerprint, instrument metadata hash, capability snapshot). DEMO enable requires valid cert; invalidate on upgrade/endpoint/credential-scope/instrument change until re-run contract+fault (+ re-evidence if trading semantics changed).
- **Rationale**: §05.5 steps 1–5; FR-009.
- **Alternatives considered**: Soft warning only (rejected); inherit LIVE eligibility from DEMO (forbidden §05.5/§06).

## R7 — Completed lifecycle definition (evidence)

- **Decision**: Count only **round-trip to flat** on real testnet: entry → fills → exit/flatten → flat, no UNKNOWN/open recon. Entry-only, cancel-before-send, mock/fault runs do **not** count.
- **Rationale**: Clarify Q2=B, Q5=A; SC-004.
- **Alternatives considered**: Count any terminal intent (rejected); mix mock into 50 (rejected).

## R8 — Soak continuity

- **Decision**: ≥72h **wall-clock** continuous DEMO process; Owner pause fails gate (restart clock); Windows sleep/resume allowed iff recovery+recon clean before new risk-increasing orders.
- **Rationale**: Clarify Q3=A; v1.4 “continuous run ≥72h”; P-04 sleep/resume.
- **Alternatives considered**: Cumulative pause-friendly runtime (rejected); ignore sleep entirely (rejected — unrealistic on Windows).

## R9 — Market data for strategy on DEMO

- **Decision**: Ingest **closed** `BTC/USDT` `15m` candles via DEMO adapter/CCXT public+auth as required; feature snapshots keep `feature_schema_version`; `rule_sma_cross_v1` unchanged params from mục 16.
- **Rationale**: FR-006; constitution VI; G4.1.
- **Alternatives considered**: Reuse Paper synthetic candles while sending DEMO orders (rejected — mismatched venue truth); open candle signals (forbidden).

## R10 — Test layering & secrets

- **Decision**: Default CI/dev = mock/injected CCXT double. Real-network markers require `AUTOTRADE_D1B_REAL=1` + keyring credentials. Never commit keys/tokens/chat IDs. Redaction unchanged.
- **Rationale**: FR-007; clarify Q5; solo safety.
- **Alternatives considered**: Always-on real network in CI (rejected — flaky/secret risk); plaintext `.env` in repo (forbidden).

## R11 — Telegram in DEMO

- **Decision**: Reuse D1a outbox/commands; every message/command path tags active `mode` (`DEMO`|`PAPER`); `/pause` → L1 only; no remote resume/flatten.
- **Rationale**: G5.4–G5.5; clarify Q1.
- **Alternatives considered**: New remote trading commands (rejected — out of D1 scope).

## R12 — What is explicitly not researched

PySide6 Broker Hub UX, installer, LIVE eligibility machine, second exchange, Backtest engine, AI/vector backends — deferred to D1c / D1.1 / D2 / D3 / D4.
