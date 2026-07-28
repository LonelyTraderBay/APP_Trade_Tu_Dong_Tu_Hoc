"""Integration: rule_sma_cross_v1 wired to real (fake-exchange) candles +
PaperAdapter execution through `run_trading_loop_iteration` — the first
place in this codebase a strategy autonomously reaches `DurableSubmitter`.

All numeric assertions below reuse the exact SC-006 reference series and
hand-derivation from `tests/unit/test_rule_sma_cross_v1.py` (closes with
high=close+1/low=close-1 -> TR=2 on every bar -> ATR=2 wherever defined ->
stop distance = k*ATR = 1.5*2 = 3.0; n_fast=2, n_slow=4, atr_period=2,
cooldown=3 -> ENTER_LONG at i=7 (index 6), EXIT_LONG at i=10 (index 9),
cooldown through i=11..13 (index 10..12), re-entry at i=15 (index 14)).
This test module adds the plumbing (fake exchange -> DB -> features ->
strategy -> DurableSubmitter -> PaperAdapter fill), not new SMA/ATR math.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.adapters.paper import PaperAdapter
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.core.domain.money import d
from autotrade.core.oms.trading_loop import (
    DEFAULT_KS_SCOPE,
    IterationResult,
    run_trading_loop_iteration,
    seed_strategy_state,
)
from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.core.strategy.rule_sma_cross_v1 import RuleSmaCrossV1, StrategyParams
from autotrade.persistence.models import FeatureSnapshot as FeatureSnapshotRow
from autotrade.persistence.models import MarketCandle, OrderIntent, PositionLocal

ACCOUNT_ID = "paper1"
START_MS = 1_700_000_000_000

# Same series as tests/unit/test_rule_sma_cross_v1.py's SC-006 reference.
_REFERENCE_CLOSES = [10, 9, 8, 7, 6, 7, 8, 9, 8, 7, 6, 5, 4, 5, 6]
_PARAMS = StrategyParams(n_fast=2, n_slow=4, atr_period=2, cooldown=3)


def _row(i: int, close: int) -> list[Any]:
    """One ccxt-shaped OHLCV row: [ts_ms, open, high, low, close, volume].
    high=close+1/low=close-1 to preserve the reference series' TR=2/ATR=2
    hand-derivation."""
    ts = START_MS + i * 900_000
    return [ts, close, close + 1, close - 1, close, 10]


def _seed_market_candle(session: Any, i: int, close: int) -> None:
    row = _row(i, close)
    session.add(
        MarketCandle(
            symbol=D1B_ALLOWLIST.symbol,
            timeframe=D1B_ALLOWLIST.timeframe,
            open_time=datetime.fromtimestamp(row[0] / 1000, tz=UTC),
            open=d(str(row[1])),
            high=d(str(row[2])),
            low=d(str(row[3])),
            close=d(str(row[4])),
            volume=d(str(row[5])),
            is_closed=True,
        )
    )


def _adapters() -> tuple[FakeCcxtExchange, CcxtDemoAdapter, PaperAdapter]:
    fake = FakeCcxtExchange()
    market_adapter = CcxtDemoAdapter(exchange=fake, endpoint=D1B_ALLOWLIST.endpoint_class)
    exec_adapter = PaperAdapter(last_price=d("999"))  # deliberately wrong starting price
    return fake, market_adapter, exec_adapter


def _run(
    uow: Any, market_adapter: Any, exec_adapter: Any, rule: RuleSmaCrossV1
) -> IterationResult:
    return run_trading_loop_iteration(
        uow, market_adapter, exec_adapter, rule, account_id=ACCOUNT_ID
    )


@pytest.mark.d1a
def test_full_multi_iteration_run_persists_and_trades(migrated_uow) -> None:  # noqa: ANN001
    uow = migrated_uow
    fake, market_adapter, exec_adapter = _adapters()
    rule = RuleSmaCrossV1(_PARAMS)

    with uow.session() as session:
        seed_strategy_state(
            session,
            rule,
            account_id=ACCOUNT_ID,
            symbol=D1B_ALLOWLIST.symbol,
            timeframe=D1B_ALLOWLIST.timeframe,
        )
    # Nothing persisted yet -> seeding is a safe no-op on a first-ever run.
    assert rule._in_position is False
    assert rule._prev_fast is None

    def _poll(i: int, close: int) -> IterationResult:
        fake.ohlcv.append(_row(i, close))
        return run_trading_loop_iteration(
            uow, market_adapter, exec_adapter, rule, account_id=ACCOUNT_ID
        )

    def _position_qty() -> Any:
        with uow.session() as session:
            pos = (
                session.query(PositionLocal)
                .filter_by(account_id=ACCOUNT_ID, symbol=D1B_ALLOWLIST.symbol)
                .one_or_none()
            )
            return d(str(pos.qty)) if pos is not None else d("0")

    # index 0..5 (i=1..6): insufficient history then no_cross — hand-derived
    # ABSTAIN throughout per test_rule_sma_cross_v1.py's SC-006 table.
    results = [_poll(i, close) for i, close in enumerate(_REFERENCE_CLOSES[:6])]
    assert [r.error for r in results] == [None] * 6
    assert [r.new_candles_ingested for r in results] == [1] * 6
    assert [r.signal for r in results] == ["ABSTAIN"] * 6
    assert _position_qty() == d("0")

    # index 6 (i=7): the hand-derived ENTER_LONG bar.
    entry = _poll(6, _REFERENCE_CLOSES[6])
    assert entry.error is None
    assert entry.signal == "ENTER_LONG"
    assert entry.submit_result is not None
    assert entry.submit_result.ok is True

    # PAPER fill must be priced off the REAL fetched close (8), not the
    # PaperAdapter's original last_price=999 it was constructed with.
    fill_price = d(entry.submit_result.order["avg_price"])
    assert d("7.9") < fill_price < d("8.1")
    assert _position_qty() == d("0.001")

    with uow.session() as session:
        intent = session.get(OrderIntent, entry.submit_result.intent_id)
        # stop_price = last_close(8) - k*ATR(3.0) = 5.0, hand-derived exactly
        # as in test_rule_sma_cross_v1.py::test_atr_stop_distance_equals_k_times_atr_on_entry
        # (compared numerically — the DB round-trip through Numeric(24,12)
        # widens the string's trailing zeros, e.g. "5.0000000000000").
        assert d(intent.protection_spec["stop_price"]) == d("5.0")

    # index 7..8 (i=8..9): still in position, no cross.
    for i in (7, 8):
        r = _poll(i, _REFERENCE_CLOSES[i])
        assert r.signal == "ABSTAIN"
        assert r.submit_result is None
    assert _position_qty() == d("0.001")

    # index 9 (i=10): the hand-derived EXIT_LONG bar.
    exit_ = _poll(9, _REFERENCE_CLOSES[9])
    assert exit_.signal == "EXIT_LONG"
    assert exit_.submit_result is not None
    assert exit_.submit_result.ok is True
    assert abs(_position_qty()) < d("0.0000001")

    # index 10..12 (i=11..13): exactly params.cooldown=3 ABSTAIN("cooldown") bars.
    for i in (10, 11, 12):
        r = _poll(i, _REFERENCE_CLOSES[i])
        assert r.signal == "ABSTAIN"
        assert r.submit_result is None
    assert abs(_position_qty()) < d("0.0000001")

    # index 13 (i=14): cooldown expired, ordinary no_cross resumes.
    r13 = _poll(13, _REFERENCE_CLOSES[13])
    assert r13.signal == "ABSTAIN"
    assert r13.submit_result is None

    # index 14 (i=15): re-entry now that cooldown has elapsed.
    resumed_entry = _poll(14, _REFERENCE_CLOSES[14])
    assert resumed_entry.signal == "ENTER_LONG"
    assert resumed_entry.submit_result is not None
    assert resumed_entry.submit_result.ok is True
    assert _position_qty() == d("0.001")

    with uow.session() as session:
        assert session.query(MarketCandle).count() == len(_REFERENCE_CLOSES)
        assert session.query(FeatureSnapshotRow).count() == len(_REFERENCE_CLOSES)


@pytest.mark.d1a
def test_restart_seeding_prevents_double_entry(migrated_uow) -> None:  # noqa: ANN001
    uow = migrated_uow
    prefix = _REFERENCE_CLOSES[:6]  # i=1..6 -> "no_cross" per hand-derivation

    with uow.session() as session:
        for i, close in enumerate(prefix):
            _seed_market_candle(session, i, close)
        session.add(
            PositionLocal(
                account_id=ACCOUNT_ID,
                symbol=D1B_ALLOWLIST.symbol,
                qty=d("0.001"),
                provenance={"source": "prior_process_run"},
            )
        )

    rule = RuleSmaCrossV1(_PARAMS)  # freshly constructed — defaults would be _in_position=False
    assert rule._in_position is False

    with uow.session() as session:
        seed_strategy_state(
            session,
            rule,
            account_id=ACCOUNT_ID,
            symbol=D1B_ALLOWLIST.symbol,
            timeframe=D1B_ALLOWLIST.timeframe,
        )

    # Restored from the real PositionLocal row, not left at the dataclass default.
    assert rule._in_position is True
    # Hand-derived: closes[0:6]=[10,9,8,7,6,7] -> sma_fast=avg(6,7)=6.5, sma_slow=avg(8,7,6,7)=7.0.
    assert rule._prev_fast == d("6.5")
    assert rule._prev_slow == d("7.0")

    fake = FakeCcxtExchange()
    for i, close in enumerate(prefix):
        fake.ohlcv.append(_row(i, close))
    market_adapter = CcxtDemoAdapter(exchange=fake, endpoint=D1B_ALLOWLIST.endpoint_class)
    exec_adapter = PaperAdapter()

    # i=7 (index 6): close=8 -> fast=avg(7,8)=7.5 crosses above slow=avg(7,6,7,8)=7.0 —
    # a real bullish cross, per the SC-006 hand-derivation this is normally ENTER_LONG.
    fake.ohlcv.append(_row(6, _REFERENCE_CLOSES[6]))
    result = _run(uow, market_adapter, exec_adapter, rule)

    assert result.new_candles_ingested == 1
    # But the strategy already (correctly) believes it is long -> no spurious re-entry.
    assert result.signal == "ABSTAIN"
    assert result.submit_result is None
    assert rule._in_position is True


@pytest.mark.d1a
def test_ks_elevated_blocks_entry(migrated_uow) -> None:  # noqa: ANN001
    uow = migrated_uow
    with uow.session() as session:
        ks = KillSwitch(scope=DEFAULT_KS_SCOPE)
        ks.raise_to(1, reason="test_block_entry")
        ks.persist(session)

    fake, market_adapter, exec_adapter = _adapters()
    rule = RuleSmaCrossV1(_PARAMS)

    results: list[IterationResult] = []
    for i, close in enumerate(_REFERENCE_CLOSES[:7]):  # through the ENTER_LONG bar
        fake.ohlcv.append(_row(i, close))
        results.append(_run(uow, market_adapter, exec_adapter, rule))

    entry_attempt = results[6]
    assert entry_attempt.signal == "ENTER_LONG"  # the strategy still genuinely fires
    assert entry_attempt.submit_result is not None
    assert entry_attempt.submit_result.ok is False  # but the KS gate blocks it
    assert entry_attempt.error is not None  # not silently dropped

    with uow.session() as session:
        pos = (
            session.query(PositionLocal)
            .filter_by(account_id=ACCOUNT_ID, symbol=D1B_ALLOWLIST.symbol)
            .one_or_none()
        )
    assert pos is None or abs(d(str(pos.qty))) < d("1e-9")


@pytest.mark.d1a
def test_ks_elevated_still_allows_exit_long(migrated_uow) -> None:  # noqa: ANN001
    """Owner decision (2026-07-28, post-review of `trading_loop.py`):
    `EXIT_LONG` submits with `reduce_only=True`, matching the manual Flatten
    button's T042 Decision 2 opt-in — a strategy-driven exit is exposure-
    REDUCING and must keep working while the kill-switch is elevated (L1+),
    same v1.4 L3 intent already applied to Flatten. `ENTER_LONG` stays
    unaffected: a fresh entry must still be blocked by an elevated KS."""
    uow = migrated_uow
    fake, market_adapter, exec_adapter = _adapters()
    rule = RuleSmaCrossV1(_PARAMS)

    results: list[IterationResult] = []
    for i, close in enumerate(_REFERENCE_CLOSES[:7]):
        fake.ohlcv.append(_row(i, close))
        results.append(_run(uow, market_adapter, exec_adapter, rule))
    assert results[6].signal == "ENTER_LONG"
    assert results[6].submit_result.ok is True

    # Raise the kill switch before the bearish-cross exit bar arrives.
    with uow.session() as session:
        ks = KillSwitch(scope=DEFAULT_KS_SCOPE)
        ks.raise_to(2, reason="test_exit_still_allowed")
        ks.persist(session)

    for i in range(7, 10):
        fake.ohlcv.append(_row(i, _REFERENCE_CLOSES[i]))
        results.append(_run(uow, market_adapter, exec_adapter, rule))

    exit_attempt = results[9]
    assert exit_attempt.signal == "EXIT_LONG"  # strategy correctly wants out
    assert exit_attempt.submit_result is not None
    assert exit_attempt.submit_result.ok is True  # reduce_only bypasses the KS block
    assert exit_attempt.error is None

    # The real position actually closed, because the exit went through.
    with uow.session() as session:
        pos = (
            session.query(PositionLocal)
            .filter_by(account_id=ACCOUNT_ID, symbol=D1B_ALLOWLIST.symbol)
            .one()
        )
    assert pos.qty == d("0")


@pytest.mark.d1a
def test_ks_elevated_still_blocks_enter_long(migrated_uow) -> None:  # noqa: ANN001
    """The other half of the same decision: `ENTER_LONG` is NOT
    `reduce_only` and must still be blocked while KS is elevated — only
    exposure-reducing exits get the bypass."""
    uow = migrated_uow
    fake, market_adapter, exec_adapter = _adapters()
    rule = RuleSmaCrossV1(_PARAMS)

    with uow.session() as session:
        ks = KillSwitch(scope=DEFAULT_KS_SCOPE)
        ks.raise_to(1, reason="test_block_entry")
        ks.persist(session)

    results: list[IterationResult] = []
    for i, close in enumerate(_REFERENCE_CLOSES[:7]):
        fake.ohlcv.append(_row(i, close))
        results.append(_run(uow, market_adapter, exec_adapter, rule))

    entry_attempt = results[6]
    assert entry_attempt.signal == "ENTER_LONG"
    assert entry_attempt.submit_result is not None
    assert entry_attempt.submit_result.ok is False
    # `AccountGate.allows_exposure_increase` is False once status is
    # SAFE_LOCK (ks_level >= 1), so a "buy" is refused by `DurableSubmitter`'s
    # earlier `account_not_ready` gate before `RiskEngine.check_increase`'s
    # own `kill_switch_blocks_entry` reason is ever reached — still a hard
    # block, just via the gate check rather than the risk-decision reason.
    assert entry_attempt.submit_result.error == "account_not_ready"

    with uow.session() as session:
        pos = (
            session.query(PositionLocal)
            .filter_by(account_id=ACCOUNT_ID, symbol=D1B_ALLOWLIST.symbol)
            .one_or_none()
        )
    assert pos is None or pos.qty == d("0")


@pytest.mark.d1a
def test_idempotent_candle_ingestion(migrated_uow) -> None:  # noqa: ANN001
    uow = migrated_uow
    fake, market_adapter, exec_adapter = _adapters()
    rule = RuleSmaCrossV1(_PARAMS)

    fake.ohlcv.append(_row(0, 10))
    r1 = _run(uow, market_adapter, exec_adapter, rule)
    assert r1.new_candles_ingested == 1
    assert r1.error is None

    # Re-fetch of the SAME rolling window (normal between two 60s polls of a
    # still-open 15m candle) — must not raise on the unique constraint, and
    # must report nothing new.
    r2 = _run(uow, market_adapter, exec_adapter, rule)
    assert r2.new_candles_ingested == 0
    assert r2.signal is None  # cheaply skipped, not re-evaluated
    assert r2.error is None

    # An overlapping window: one already-known candle + one genuinely new one.
    fake.ohlcv.append(_row(1, 9))
    r3 = _run(uow, market_adapter, exec_adapter, rule)
    assert r3.new_candles_ingested == 1

    with uow.session() as session:
        assert session.query(MarketCandle).count() == 2


@pytest.mark.d1a
def test_submit_exception_is_caught_not_propagated(migrated_uow) -> None:  # noqa: ANN001
    uow = migrated_uow
    fake = FakeCcxtExchange()
    market_adapter = CcxtDemoAdapter(exchange=fake, endpoint=D1B_ALLOWLIST.endpoint_class)

    class RaisingPaperAdapter(PaperAdapter):
        def place_order(  # type: ignore[override]
            self,
            *,
            client_order_id: str,
            symbol: str,
            side: str,
            qty: Any,
            order_type: str = "market",
        ) -> dict[str, Any]:
            raise RuntimeError("simulated exec adapter failure")

    exec_adapter = RaisingPaperAdapter()
    rule = RuleSmaCrossV1(_PARAMS)

    results: list[IterationResult] = []
    for i, close in enumerate(_REFERENCE_CLOSES[:7]):
        fake.ohlcv.append(_row(i, close))
        results.append(_run(uow, market_adapter, exec_adapter, rule))

    entry_attempt = results[6]
    assert entry_attempt.signal == "ENTER_LONG"
    assert entry_attempt.submit_result is not None
    assert entry_attempt.submit_result.ok is False
    assert entry_attempt.error is not None
    assert "simulated exec adapter failure" in entry_attempt.error


@pytest.mark.d1a
def test_market_data_fetch_failure_is_caught_not_propagated(migrated_uow) -> None:  # noqa: ANN001
    """Exercises this module's OWN top-level catch-all directly (as opposed
    to `test_submit_exception_is_caught_not_propagated`, where the exception
    is already caught one layer down inside `DurableSubmitter.submit`) — a
    network hiccup fetching OHLCV must not crash the poll loop either."""
    uow = migrated_uow

    class RaisingMarketAdapter:
        connected = True

        def connect(self) -> None:
            return None

        def fetch_ohlcv_closed(self, *, limit: int = 100) -> list[dict[str, Any]]:
            raise RuntimeError("simulated network failure")

    exec_adapter = PaperAdapter()
    rule = RuleSmaCrossV1(_PARAMS)

    result = run_trading_loop_iteration(
        uow, RaisingMarketAdapter(), exec_adapter, rule, account_id=ACCOUNT_ID
    )
    assert result.new_candles_ingested == 0
    assert result.error is not None
    assert "simulated network failure" in result.error
