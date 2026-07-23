"""Incomplete recovery stays locked; KS not lowered."""

from __future__ import annotations

import pytest

from autotrade.core.oms.account_state import AccountStatus
from autotrade.core.oms.recovery import run_startup_recovery
from autotrade.core.risk.kill_switch import KillSwitch


@pytest.mark.d1a
def test_startup_recovery_incomplete(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
    _ = risk
    ks = KillSwitch(scope="account:paper1", level=2, latched=True)
    with uow.session() as session:
        ks.persist(session)

    result = run_startup_recovery(
        uow=uow,
        adapter=adapter,
        gate=gate,
        ks=ks,
        auth_ok=False,
        pagination_complete=False,
        data_fresh=False,
    )
    assert result.ready is False
    assert gate.status == AccountStatus.SAFE_LOCK
    assert gate.allows_exposure_increase is False
    assert ks.level >= 2


@pytest.mark.d1a
def test_startup_recovery_success(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
    _ = risk
    gate.begin_recovery()
    ks = KillSwitch(scope="account:paper1")
    result = run_startup_recovery(
        uow=uow, adapter=adapter, gate=gate, ks=ks, auth_ok=True
    )
    assert result.ready is True
    assert gate.status == AccountStatus.READY
