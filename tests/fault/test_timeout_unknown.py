"""Timeout → UNKNOWN / MAY_HAVE_BEEN_ACCEPTED; query; no blind retry."""

from __future__ import annotations

import pytest

from autotrade.core.domain.money import d
from autotrade.core.oms.fsm import DeliveryCertainty
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest


@pytest.mark.d1a
def test_timeout_unknown_no_blind_retry(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
    calls = {"n": 0}
    original = adapter.place_order

    def counting(**kwargs):  # noqa: ANN003
        calls["n"] += 1
        return original(**kwargs)

    adapter.place_order = counting  # type: ignore[method-assign]
    submitter = DurableSubmitter(
        uow=uow,
        adapter=adapter,
        risk=risk,
        gate=gate,
        simulate_timeout_after_send=True,
    )
    result = submitter.submit(
        SubmitRequest(
            account_id="paper1",
            symbol="PAPER-INTERNAL-1",
            side="buy",
            qty=d("1"),
            price=d("100"),
        )
    )
    assert result.adapter_called is True
    assert result.delivery == DeliveryCertainty.MAY_HAVE_BEEN_ACCEPTED.value
    assert calls["n"] == 1  # place once only — resolve via query, no second place
    assert result.client_order_id is not None
    assert adapter.query_order_by_client_id(result.client_order_id) is not None
