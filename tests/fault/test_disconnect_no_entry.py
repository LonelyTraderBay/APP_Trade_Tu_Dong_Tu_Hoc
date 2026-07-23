"""Disconnect → no new exposure-increasing entry."""

from __future__ import annotations

import pytest

from autotrade.core.domain.money import d
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest


@pytest.mark.d1a
def test_disconnect_no_entry(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
    adapter.disconnect()
    submitter = DurableSubmitter(uow=uow, adapter=adapter, risk=risk, gate=gate)
    result = submitter.submit(
        SubmitRequest(
            account_id="paper1",
            symbol="PAPER-INTERNAL-1",
            side="buy",
            qty=d("1"),
            price=d("100"),
        )
    )
    assert result.ok is False
    assert adapter.get_positions() == []
