"""DEMO timeout → UNKNOWN; no blind retry."""

from __future__ import annotations

from decimal import Decimal

import pytest

from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.core.domain.money import d
from autotrade.core.oms.account_state import AccountGate
from autotrade.core.oms.fsm import DeliveryCertainty
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest
from autotrade.core.risk.engine import RiskEngine


@pytest.mark.d1b
def test_demo_timeout_unknown_no_blind_retry(migrated_uow) -> None:  # noqa: ANN001
    fake = FakeCcxtExchange(last_price=d("50000"), timeout_after_send=True)
    adapter = CcxtDemoAdapter(exchange=fake, endpoint="binance_spot_testnet")
    adapter.connect()
    gate = AccountGate(account_id="demo1")
    gate.mark_ready()
    calls = {"n": 0}
    original = adapter.place_order

    def counting(**kwargs):  # noqa: ANN003
        calls["n"] += 1
        return original(**kwargs)

    adapter.place_order = counting  # type: ignore[method-assign]
    submitter = DurableSubmitter(
        uow=migrated_uow,
        adapter=adapter,
        risk=RiskEngine(),
        gate=gate,
        simulate_timeout_after_send=True,
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
    assert result.adapter_called is True
    assert result.delivery == DeliveryCertainty.MAY_HAVE_BEEN_ACCEPTED.value
    assert calls["n"] == 1
