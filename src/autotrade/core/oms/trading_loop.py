"""Single-poll live trading-loop iteration — PAPER execution, real market data.

**Scope (owner-locked, see task brief)**: PAPER mode only. `DEMO`/real-order
wiring is explicitly out of scope here and this module never constructs or
accepts a `CcxtDemoAdapter` as an *execution* adapter — only as a read-only
market-data source (`market_adapter`, typed via the local `MarketDataAdapter`
protocol below, never `place_order`-called by this module). `exec_adapter`
is typed as the concrete `PaperAdapter`, not the generic `BrokerAdapter`
protocol: this is a deliberate type-level guard, not an oversight — a caller
cannot wire a `CcxtDemoAdapter` in as `exec_adapter` without an obvious type
violation, so "refuse to trade a non-PAPER account" is enforced by the
signature itself rather than a runtime `Account.mode` check inside this
module (resolving *which* account is active — `get_active_account` — is a
caller-level concern; see module docstring precedent in
`app_ui/controllers/kill_switch.py`).

**Why `exec_adapter.last_price` gets mutated here**: `PaperAdapter.place_order`
fills against `self.last_price`, *not* the `price=` argument on
`SubmitRequest` (that field only feeds the pre-trade risk/notional check).
A `PaperAdapter` constructed once and left untouched would fill every order
at whatever `last_price` it was constructed with, completely disconnected
from the real OHLCV this module fetches — defeating the entire point of the
"real market data, fake execution" hybrid design. So this module sets
`exec_adapter.last_price` to the latest closed candle's close immediately
before every submit, so PAPER fills actually track real prices.

**Two pieces of process-restart state this module owns**:

1. `RuleSmaCrossV1` is a *stateful* object (`_prev_fast`/`_prev_slow`/
   `_in_position`/`_cooldown_left` mutate on every `.evaluate()` call). The
   caller must hold ONE instance across all polls in a process (this module
   never constructs one internally) — a fresh instance every call loses
   crossover memory and can never detect a cross.
2. `seed_strategy_state()` re-derives that in-memory state after a process
   restart: `_in_position` from the real `PositionLocal` row (so a restart
   while actually holding a position cannot spuriously double-enter), and
   `_prev_fast`/`_prev_slow` from one `FeatureEngine.snapshot()` over
   whatever closed candles already exist in `market_candles` (so crossover
   detection doesn't need to "warm up" again after a restart if there is
   already enough persisted history). `_cooldown_left` is NOT reconstructed
   — it always restarts at its dataclass default (0). This is a documented,
   accepted simplification: the worst case is a new entry becomes eligible
   slightly earlier than a strict cooldown window would normally allow right
   after a restart. Not a safety violation (every other risk/KS gate below
   still applies to that entry) — just a minor strategy-fidelity nuance,
   because a position tells you *whether* you are in a trade, not *when* you
   last exited one.

**Position sizing is a placeholder, not a decision**: `DEFAULT_ENTRY_QTY`
below is a small, dust-safe constant (mirrors the same
`Decimal("0.001")` default `core.certify.real_lifecycles.
run_round_trip_lifecycles` uses for DEMO evidence trades) so the strategy
can submit a real, safe-magnitude order. No position-sizing logic (risk-%,
ATR-based, volatility-scaled, ...) exists anywhere in this codebase yet —
this is not a sized trading decision, it is scaffolding.

**Owner decision (2026-07-28, post-review of this module): `EXIT_LONG` is
`reduce_only=True`.** `RiskEngine.check_increase`'s `ks_level >= 1 and not
reduce_only` check has no notion of order *direction* by default — a plain
`EXIT_LONG` sell that is *reducing* an existing long would otherwise be
rejected exactly like a fresh entry whenever the kill-switch is elevated
(L1+). `reduce_only=True` was originally scoped narrowly to the manual
Flatten button's full-close path (`core.oms.flatten`, T042 Decision 2); the
Owner explicitly extended that same opt-in to a strategy-driven `EXIT_LONG`
here, matching v1.4's L3 intent ("reduce-only flatten" must keep working
while KS is elevated) — every other `check_increase` limit (qty/notional)
still applies unchanged, only the `kill_switch_blocks_entry` reason is
skipped. `ENTER_LONG` is NOT `reduce_only` — a fresh entry must still be
blocked by an elevated kill-switch, same as always.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.orm import Session

from autotrade.core.adapters.paper import PaperAdapter
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.core.domain.ids import IdFactory
from autotrade.core.domain.money import d
from autotrade.core.features.engine import FeatureEngine
from autotrade.core.market.candles import Candle
from autotrade.core.oms.account_state import AccountGate, AccountStatus
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest, SubmitResult
from autotrade.core.risk.engine import RiskEngine
from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.core.strategy.rule_sma_cross_v1 import RuleSmaCrossV1
from autotrade.persistence.models import FeatureSnapshot as FeatureSnapshotRow
from autotrade.persistence.models import MarketCandle, PositionLocal
from autotrade.persistence.uow import UnitOfWork

#: Placeholder position-sizing constant — see module docstring. NOT a sized
#: trading decision; mirrors `core.certify.real_lifecycles`'s dust-safe
#: evidence-trade default.
DEFAULT_ENTRY_QTY: Decimal = d("0.001")

#: Same "flat" threshold used throughout OMS (`core.oms.flatten`,
#: `core.certify.real_lifecycles`, `core.accounts.active`).
_FLAT_EPSILON: Decimal = d("1e-12")

#: Same value as `app_ui/controllers/tray.py::DEFAULT_KS_SCOPE` /
#: `app_ui/services/startup.py::DEFAULT_KS_SCOPE` — the one kill-switch
#: scope that gates trading app-wide today. Re-declared (not imported) here
#: deliberately: `core/*` must not depend on `app_ui/*` (the dependency runs
#: the other way in this codebase).
DEFAULT_KS_SCOPE = "global"


@runtime_checkable
class MarketDataAdapter(Protocol):
    """Structural type for the read-only OHLCV source.

    Deliberately NOT an import of `CcxtDemoAdapter` by name: keeps
    `core/oms` free of any dependency on the `ccxt_demo` adapter package,
    matching the boundary documented at the top of
    `core/adapters/ccxt_demo/adapter.py` ("Strategy/Risk/OMS must never
    import this module's `ccxt` dependency directly"). `CcxtDemoAdapter`
    satisfies this protocol structurally without either module importing
    the other by name.
    """

    connected: bool

    def connect(self) -> None: ...

    def fetch_ohlcv_closed(self, *, limit: int = 100) -> list[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class IterationResult:
    """What happened during one `run_trading_loop_iteration` call.

    Typed, never a bare exception — safe to call in a tight poll loop.
    `signal` is `None` when this cycle cheaply skipped strategy evaluation
    entirely (no new closed candle since the last poll — see
    `run_trading_loop_iteration`), and one of `"ENTER_LONG"` / `"EXIT_LONG"`
    / `"ABSTAIN"` whenever the strategy actually ran.
    """

    new_candles_ingested: int
    signal: str | None = None
    submit_result: SubmitResult | None = None
    error: str | None = None


def seed_strategy_state(
    session: Session,
    rule: RuleSmaCrossV1,
    *,
    account_id: str,
    symbol: str = D1B_ALLOWLIST.symbol,
    timeframe: str = D1B_ALLOWLIST.timeframe,
) -> None:
    """Restart-safety seed for a freshly constructed `RuleSmaCrossV1`.

    Call this EXACTLY ONCE, before the very first call to
    `run_trading_loop_iteration` in a process — never again afterwards (a
    second call would clobber live in-memory crossover state this same
    function just seeded with a possibly-stale re-read). Ownership of
    calling this exactly once belongs to the caller (the CLI poll-loop
    wrapper), not this module.

    Seeds two independent pieces of state:

    - `_in_position`, from the real `PositionLocal` row for
      `account_id`/`symbol` (qty defaults to 0 if no row exists) — so a
      process restart while an actual position is open does not
      misreport itself as flat and risk a spurious double-entry.
    - `_prev_fast`/`_prev_slow`, from one `FeatureEngine.snapshot()` over
      whatever closed candles for `symbol`/`timeframe` already exist in
      `market_candles` (a no-op if none exist yet, or if there is not yet
      enough history for both SMAs to be defined — in that case the
      strategy simply behaves as if this were the first run, which is
      correct).

    `_cooldown_left` is intentionally left at its dataclass default (0) —
    see module docstring for why that is an accepted, documented
    simplification rather than a bug.
    """
    row = (
        session.query(PositionLocal)
        .filter(PositionLocal.account_id == account_id, PositionLocal.symbol == symbol)
        .one_or_none()
    )
    qty = d(str(row.qty)) if row is not None else d("0")
    rule._in_position = abs(qty) > _FLAT_EPSILON

    candles = _load_closed_candles(session, symbol=symbol, timeframe=timeframe)
    if not candles:
        return
    snap = FeatureEngine().snapshot(
        candles,
        n_fast=rule.params.n_fast,
        n_slow=rule.params.n_slow,
        atr_period=rule.params.atr_period,
    )
    if snap is not None and snap.sma_fast is not None and snap.sma_slow is not None:
        rule._prev_fast = snap.sma_fast
        rule._prev_slow = snap.sma_slow


def run_trading_loop_iteration(
    uow: UnitOfWork,
    market_adapter: MarketDataAdapter,
    exec_adapter: PaperAdapter,
    rule: RuleSmaCrossV1,
    *,
    account_id: str,
    symbol: str = D1B_ALLOWLIST.symbol,
    timeframe: str = D1B_ALLOWLIST.timeframe,
    ks_scope: str = DEFAULT_KS_SCOPE,
    fetch_limit: int = 100,
    entry_qty: Decimal = DEFAULT_ENTRY_QTY,
) -> IterationResult:
    """Run exactly one poll cycle: fetch → persist → featurize → evaluate →
    (maybe) submit through the real risk-gated `DurableSubmitter` path.

    Safe to call repeatedly and cheaply: if the fetched closed-candle window
    contains nothing new since the last call (the normal case between two
    60s polls of a 15m candle), this returns immediately after the no-op
    upsert without touching features/strategy/OMS at all — `signal` stays
    `None`. This is not just a performance nicety: `RuleSmaCrossV1.evaluate`
    mutates cooldown/crossover state on every call, so re-evaluating the
    SAME already-seen candle on every 60s poll would decay `_cooldown_left`
    far faster than the strategy's `cooldown` parameter intends. Evaluating
    once per genuinely NEW closed candle is required for correctness, not
    optional.

    Never raises: every failure mode (adapter fetch failure, DB error,
    submit failure) is caught and returned as a typed `IterationResult`
    with `error` set, so a caller's poll loop can always proceed to the
    next cycle.

    `rule`, `market_adapter`, and `exec_adapter` must be the SAME instances
    across repeated calls within one process (this function never
    constructs them) — see module docstring. `AccountGate`/`RiskEngine`/
    `DurableSubmitter` are, by contrast, deliberately rebuilt fresh on every
    call: cheap, stateless, and the gate's status must reflect the REAL
    persisted kill-switch level as of *this* poll, not a stale snapshot.
    """
    try:
        if not market_adapter.connected:
            market_adapter.connect()
        if not exec_adapter.connected:
            exec_adapter.connect()

        fetched = market_adapter.fetch_ohlcv_closed(limit=fetch_limit)

        with uow.session() as session:
            inserted = _upsert_candles(session, fetched)
            if inserted == 0:
                return IterationResult(new_candles_ingested=0)

            history = _load_closed_candles(session, symbol=symbol, timeframe=timeframe)
            snap = FeatureEngine().snapshot(
                history,
                n_fast=rule.params.n_fast,
                n_slow=rule.params.n_slow,
                atr_period=rule.params.atr_period,
            )
            if snap is not None:
                session.add(
                    FeatureSnapshotRow(
                        feature_schema_version=snap.feature_schema_version,
                        event_time=snap.event_time,
                        symbol=snap.symbol,
                        payload_hash=snap.payload_hash,
                        payload_ref=None,
                    )
                )

            ks_level = KillSwitch.load(session, ks_scope).level
            pos_row = (
                session.query(PositionLocal)
                .filter(PositionLocal.account_id == account_id, PositionLocal.symbol == symbol)
                .one_or_none()
            )
            current_qty = d(str(pos_row.qty)) if pos_row is not None else d("0")

        decision = rule.evaluate(snap)
        last_close = history[-1].close

        gate = AccountGate(
            account_id=account_id,
            # Real, persisted kill-switch level -> the actual safety gate
            # for this whole feature. Mirrors the exact precedent in
            # `app_ui/controllers/kill_switch.py::KillSwitchController.flatten`.
            status=AccountStatus.READY if ks_level < 1 else AccountStatus.SAFE_LOCK,
        )
        risk = RiskEngine()
        submitter = DurableSubmitter(uow=uow, adapter=exec_adapter, risk=risk, gate=gate)

        submit_result: SubmitResult | None = None
        error: str | None = None

        if decision.side == "ENTER_LONG":
            # Route the PAPER fill off real market data (see module
            # docstring) — PaperAdapter.place_order fills at `last_price`,
            # not at `SubmitRequest.price`.
            exec_adapter.last_price = last_close
            stop_price = (
                last_close - decision.stop_distance
                if decision.stop_distance is not None
                else None
            )
            submit_result = submitter.submit(
                SubmitRequest(
                    account_id=account_id,
                    symbol=symbol,
                    side="buy",
                    qty=entry_qty,
                    price=last_close,
                    stop_price=stop_price,
                    signal_id=IdFactory().new("sig"),
                )
            )
        elif decision.side == "EXIT_LONG":
            if abs(current_qty) < _FLAT_EPSILON:
                # Declared state (strategy believes it is long) vs. real
                # state (PositionLocal is flat) drift — detectable but not
                # safely submittable (a zero-qty sell is meaningless).
                # Restart-seeding minimizes this but cannot fully eliminate
                # it (see `seed_strategy_state` docstring on `_cooldown_left`).
                error = (
                    "reconciliation_mismatch:strategy_believes_in_position_"
                    "but_position_local_is_flat"
                )
            else:
                exec_adapter.last_price = last_close
                submit_result = submitter.submit(
                    SubmitRequest(
                        account_id=account_id,
                        symbol=symbol,
                        side="sell",
                        qty=abs(current_qty),
                        price=last_close,
                        signal_id=IdFactory().new("sig"),
                        reduce_only=True,
                    )
                )

        if submit_result is not None and not submit_result.ok:
            error = submit_result.error

        return IterationResult(
            new_candles_ingested=inserted,
            signal=decision.side,
            submit_result=submit_result,
            error=error,
        )
    except Exception as exc:  # noqa: BLE001 - contract: never crash the poll loop
        return IterationResult(new_candles_ingested=0, error=f"iteration_failed:{exc}")


def _upsert_candles(session: Session, candles: list[dict[str, Any]]) -> int:
    """Idempotent upsert on the existing `uq_candle_window` unique
    constraint (symbol, timeframe, open_time). `market_adapter.
    fetch_ohlcv_closed(limit=...)` returns a rolling window, not just new
    candles, so the same closed candle WILL be re-fetched on later polls —
    this must not raise on that, and does not (queries by the unique key
    first rather than relying on `session.merge()`, which matches on
    primary key identity, not this table's business unique key).

    Returns the count of genuinely NEW rows inserted (a re-fetched
    already-known candle updates in place — picking up any late correction
    from the venue — and does not count as new).
    """
    inserted = 0
    for c in candles:
        open_time = datetime.fromtimestamp(c["open_time_ms"] / 1000, tz=UTC)
        existing = (
            session.query(MarketCandle)
            .filter(
                MarketCandle.symbol == c["symbol"],
                MarketCandle.timeframe == c["timeframe"],
                MarketCandle.open_time == open_time,
            )
            .one_or_none()
        )
        if existing is not None:
            existing.open = c["open"]
            existing.high = c["high"]
            existing.low = c["low"]
            existing.close = c["close"]
            existing.volume = c["volume"]
            existing.is_closed = c["is_closed"]
            continue
        session.add(
            MarketCandle(
                symbol=c["symbol"],
                timeframe=c["timeframe"],
                open_time=open_time,
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=c["volume"],
                is_closed=c["is_closed"],
            )
        )
        inserted += 1
    session.flush()
    return inserted


def _load_closed_candles(session: Session, *, symbol: str, timeframe: str) -> list[Candle]:
    """Full closed-candle history for symbol/timeframe, oldest first —
    `FeatureEngine.snapshot` needs the full trailing window (up to
    `n_slow` candles), not just whatever one fetch call returned."""
    rows = session.scalars(
        select(MarketCandle)
        .where(
            MarketCandle.symbol == symbol,
            MarketCandle.timeframe == timeframe,
            MarketCandle.is_closed.is_(True),
        )
        .order_by(MarketCandle.open_time.asc())
    ).all()
    return [
        Candle(
            symbol=row.symbol,
            timeframe=row.timeframe,
            open_time=row.open_time,
            open=d(str(row.open)),
            high=d(str(row.high)),
            low=d(str(row.low)),
            close=d(str(row.close)),
            volume=d(str(row.volume)),
            is_closed=row.is_closed,
        )
        for row in rows
    ]
