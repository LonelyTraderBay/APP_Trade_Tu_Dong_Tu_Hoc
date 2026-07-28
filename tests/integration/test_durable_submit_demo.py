"""Durable submit on DEMO adapter path."""

from __future__ import annotations

from decimal import Decimal

import pytest

from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.core.domain.money import d
from autotrade.core.oms.account_state import AccountGate
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest
from autotrade.core.risk.engine import RiskEngine
from autotrade.persistence.models import Order


@pytest.mark.d1b
def test_durable_submit_demo_before_send(migrated_uow) -> None:  # noqa: ANN001
    fake = FakeCcxtExchange(last_price=d("50000"))
    adapter = CcxtDemoAdapter(exchange=fake, endpoint="binance_spot_testnet")
    adapter.connect()
    gate = AccountGate(account_id="demo1")
    gate.mark_ready()
    submitter = DurableSubmitter(
        uow=migrated_uow, adapter=adapter, risk=RiskEngine(), gate=gate
    )
    result = submitter.submit(
        SubmitRequest(
            account_id="demo1",
            symbol=D1B_ALLOWLIST.symbol,
            side="buy",
            qty=Decimal("0.001"),
            price=d("50000"),
        )
    )
    assert result.ok
    assert result.adapter_called
    with migrated_uow.session() as session:
        order_row = session.query(Order).filter(Order.intent_id == result.intent_id).one()
        # G1.4 — CcxtDemoAdapter's normalized order dict nests the full
        # underlying ccxt payload under "raw"; confirm both the normalized
        # fields AND the nested real broker payload survive persistence.
        assert order_row.raw_reference
        assert order_row.raw_reference["broker_order_id"] == order_row.broker_order_id
        assert order_row.raw_reference["raw"]["id"] == order_row.broker_order_id
        assert order_row.raw_reference["raw"]["symbol"] == D1B_ALLOWLIST.symbol


@pytest.mark.d1b
def test_commit_fail_no_send_demo(migrated_uow) -> None:  # noqa: ANN001
    fake = FakeCcxtExchange()
    adapter = CcxtDemoAdapter(exchange=fake, endpoint="binance_spot_testnet")
    adapter.connect()
    gate = AccountGate(account_id="demo1")
    gate.mark_ready()
    submitter = DurableSubmitter(
        uow=migrated_uow,
        adapter=adapter,
        risk=RiskEngine(),
        gate=gate,
        fail_commit=True,
    )
    calls = {"n": 0}
    original = adapter.place_order

    def counting(**kwargs):  # noqa: ANN003
        calls["n"] += 1
        return original(**kwargs)

    adapter.place_order = counting  # type: ignore[method-assign]
    result = submitter.submit(
        SubmitRequest(
            account_id="demo1",
            symbol=D1B_ALLOWLIST.symbol,
            side="buy",
            qty=Decimal("0.001"),
            price=d("50000"),
        )
    )
    assert result.ok is False
    assert result.adapter_called is False
    assert calls["n"] == 0
    assert "commit" in (result.error or "").lower() or result.error