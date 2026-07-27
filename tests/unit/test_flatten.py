"""Unit tests for `autotrade.core.oms.flatten` (T042).

Uses `CcxtDemoAdapter(exchange=FakeCcxtExchange())` only — no real network,
no real ccxt. `FakeCcxtExchange._positions` is manipulated directly to seed
a starting position without depending on a prior submit succeeding.
"""

from __future__ import annotations

from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.core.domain.money import d
from autotrade.core.oms.account_state import AccountGate, AccountStatus
from autotrade.core.oms.flatten import FlattenResult, flatten_position, position_qty
from autotrade.core.oms.submit import DurableSubmitter
from autotrade.core.risk.engine import RiskEngine, RiskLimits
from autotrade.persistence.uow import UnitOfWork

SYMBOL = D1B_ALLOWLIST.symbol
ACCOUNT_ID = "demo-binance"


def _submitter(uow: UnitOfWork, *, exchange: FakeCcxtExchange | None = None) -> DurableSubmitter:
    adapter = CcxtDemoAdapter(exchange=exchange or FakeCcxtExchange())
    adapter.connect()
    gate = AccountGate(account_id=ACCOUNT_ID, status=AccountStatus.READY)
    risk = RiskEngine(limits=RiskLimits(max_notional=d("1000000"), max_qty=d("100")))
    return DurableSubmitter(uow=uow, adapter=adapter, risk=risk, gate=gate)


def test_position_qty_reads_symbol_off_adapter(migrated_uow: UnitOfWork) -> None:
    submitter = _submitter(migrated_uow)
    assert position_qty(submitter.adapter, SYMBOL) == d("0")

    submitter.adapter.exchange._positions[SYMBOL] = d("0.5")
    assert position_qty(submitter.adapter, SYMBOL) == d("0.5")


def test_flatten_already_flat_is_a_noop(migrated_uow: UnitOfWork) -> None:
    submitter = _submitter(migrated_uow)

    result = flatten_position(submitter, account_id=ACCOUNT_ID, symbol=SYMBOL, price=d("50000"))

    assert result == FlattenResult(ok=True, qty_closed=d("0"))


def test_flatten_closes_long_position_with_opposite_sell(migrated_uow: UnitOfWork) -> None:
    submitter = _submitter(migrated_uow)
    submitter.adapter.exchange._positions[SYMBOL] = d("0.02")

    result = flatten_position(submitter, account_id=ACCOUNT_ID, symbol=SYMBOL, price=d("50000"))

    assert result.ok is True
    assert result.qty_closed == d("0.02")
    assert result.error is None
    assert position_qty(submitter.adapter, SYMBOL) == d("0")


def test_flatten_closes_short_position_with_opposite_buy(migrated_uow: UnitOfWork) -> None:
    submitter = _submitter(migrated_uow)
    submitter.adapter.exchange._positions[SYMBOL] = d("-0.02")

    result = flatten_position(submitter, account_id=ACCOUNT_ID, symbol=SYMBOL, price=d("50000"))

    assert result.ok is True
    assert result.qty_closed == d("0.02")
    assert position_qty(submitter.adapter, SYMBOL) == d("0")


def test_flatten_submit_failure_surfaces_as_typed_error(migrated_uow: UnitOfWork) -> None:
    exchange = FakeCcxtExchange(disconnect=True)
    submitter = _submitter(migrated_uow, exchange=exchange)
    submitter.adapter.exchange._positions[SYMBOL] = d("0.02")

    result = flatten_position(submitter, account_id=ACCOUNT_ID, symbol=SYMBOL, price=d("50000"))

    assert result.ok is False
    assert result.error is not None
    assert result.qty_closed is None
    # Order never filled — position must be untouched.
    assert position_qty(submitter.adapter, SYMBOL) == d("0.02")


def test_flatten_proceeds_when_kill_switch_elevated_via_gate(migrated_uow: UnitOfWork) -> None:
    """End-to-end proof (Decision 2): a non-READY gate (the proxy this
    codebase uses for an elevated kill-switch — see submit.py) still lets a
    flatten through, because `flatten_position` submits `reduce_only=True`."""
    adapter = CcxtDemoAdapter(exchange=FakeCcxtExchange())
    adapter.connect()
    adapter.exchange._positions[SYMBOL] = d("0.01")
    gate = AccountGate(account_id=ACCOUNT_ID, status=AccountStatus.SAFE_LOCK)
    risk = RiskEngine(limits=RiskLimits(max_notional=d("1000000"), max_qty=d("100")))
    submitter = DurableSubmitter(uow=migrated_uow, adapter=adapter, risk=risk, gate=gate)

    result = flatten_position(submitter, account_id=ACCOUNT_ID, symbol=SYMBOL, price=d("50000"))

    assert result.ok is True
    assert result.qty_closed == d("0.01")
