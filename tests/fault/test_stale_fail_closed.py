"""Stale data → fail-closed, no exposure increase."""

from __future__ import annotations

import pytest

from autotrade.core.domain.money import d
from autotrade.core.oms.account_state import AccountStatus
from autotrade.core.oms.recovery import run_startup_recovery
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest
from autotrade.core.risk.kill_switch import KillSwitch


@pytest.mark.d1a
def test_stale_fail_closed(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
    ks = KillSwitch(scope="account:paper1")
    run_startup_recovery(
        uow=uow,
        adapter=adapter,
        gate=gate,
        ks=ks,
        data_fresh=False,
    )
    assert gate.status == AccountStatus.SAFE_LOCK
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
    assert "not_ready" in (result.error or "")
