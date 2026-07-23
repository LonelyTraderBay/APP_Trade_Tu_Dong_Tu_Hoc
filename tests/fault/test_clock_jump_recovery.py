"""Clock jump → recovery subset before trade."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from autotrade.core.domain.clock import FrozenClock
from autotrade.core.oms.account_state import AccountStatus
from autotrade.core.oms.recovery import run_startup_recovery
from autotrade.core.risk.kill_switch import KillSwitch


@pytest.mark.d1a
def test_clock_jump_recovery(ready_paper) -> None:  # noqa: ANN001
    uow, adapter, gate, risk = ready_paper
    _ = risk
    clock = FrozenClock(datetime(2026, 7, 23, 4, 0, tzinfo=UTC), mono=0.0)
    clock.advance_mono(3600)  # simulate jump / sleep resume
    assert clock.monotonic() == 3600
    gate.begin_recovery()
    ks = KillSwitch(scope="account:paper1")
    result = run_startup_recovery(uow=uow, adapter=adapter, gate=gate, ks=ks)
    assert result.ready is True
    assert gate.status == AccountStatus.READY
