"""Commit fail → no adapter call."""

from __future__ import annotations

import pytest

from autotrade.core.domain.money import d
from autotrade.core.oms.account_state import AccountStatus
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest


@pytest.mark.d1a
def test_commit_fail_no_send(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
    calls = {"n": 0}
    original = adapter.place_order

    def wrapped(**kwargs):  # noqa: ANN003
        calls["n"] += 1
        return original(**kwargs)

    adapter.place_order = wrapped  # type: ignore[method-assign]
    submitter = DurableSubmitter(
        uow=uow, adapter=adapter, risk=risk, gate=gate, fail_commit=True
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
    assert result.ok is False
    assert result.adapter_called is False
    assert calls["n"] == 0
    assert gate.status == AccountStatus.SAFE_LOCK
