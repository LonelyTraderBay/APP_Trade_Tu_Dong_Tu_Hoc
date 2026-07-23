"""Disk / commit failure → SAFE_LOCK, no new submit."""

from __future__ import annotations

import pytest

from autotrade.core.domain.money import d
from autotrade.core.oms.account_state import AccountStatus
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest


@pytest.mark.d1a
def test_disk_safe_lock(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
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
    assert result.adapter_called is False
    assert gate.status == AccountStatus.SAFE_LOCK

    # Further increases blocked
    submitter2 = DurableSubmitter(uow=uow, adapter=adapter, risk=risk, gate=gate)
    blocked = submitter2.submit(
        SubmitRequest(
            account_id="paper1",
            symbol="PAPER-INTERNAL-1",
            side="buy",
            qty=d("1"),
            price=d("100"),
        )
    )
    assert blocked.ok is False
