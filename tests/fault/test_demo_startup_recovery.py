"""DEMO startup recovery smoke — connect then READY; auth fail → lock."""

from __future__ import annotations

import pytest

from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.oms.account_state import AccountGate, AccountStatus
from autotrade.core.oms.recovery import run_startup_recovery
from autotrade.core.risk.kill_switch import KillSwitch


@pytest.mark.d1b
def test_demo_startup_recovery_ready_when_clean(migrated_uow) -> None:  # noqa: ANN001
    adapter = CcxtDemoAdapter(exchange=FakeCcxtExchange(), endpoint="binance_spot_testnet")
    gate = AccountGate(account_id="demo1")
    ks = KillSwitch(scope="demo1")
    result = run_startup_recovery(
        uow=migrated_uow,
        adapter=adapter,
        gate=gate,
        ks=ks,
        auth_ok=True,
        pagination_complete=True,
        data_fresh=True,
        unresolved_breaks=False,
    )
    assert result.ready is True
    assert gate.status == AccountStatus.READY


@pytest.mark.d1b
def test_demo_startup_recovery_locks_on_auth_fail(migrated_uow) -> None:  # noqa: ANN001
    adapter = CcxtDemoAdapter(
        exchange=FakeCcxtExchange(fail_auth=True), endpoint="binance_spot_testnet"
    )
    gate = AccountGate(account_id="demo1")
    ks = KillSwitch(scope="demo1")
    result = run_startup_recovery(
        uow=migrated_uow,
        adapter=adapter,
        gate=gate,
        ks=ks,
        auth_ok=False,
    )
    assert result.ready is False
    assert gate.status == AccountStatus.SAFE_LOCK
