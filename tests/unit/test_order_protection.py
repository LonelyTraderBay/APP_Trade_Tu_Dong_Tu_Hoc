"""Protection sync / failure escalation."""

from __future__ import annotations

from autotrade.core.adapters.paper import PaperAdapter
from autotrade.core.domain.money import d
from autotrade.core.oms.account_state import AccountGate, AccountStatus
from autotrade.core.oms.protection import sync_protection


def test_protection_ok_and_failure_locks() -> None:
    adapter = PaperAdapter()
    adapter.connect()
    gate = AccountGate("a1")
    gate.mark_ready()
    ok = sync_protection(
        adapter,
        gate,
        client_order_id="c1",
        symbol="PAPER-INTERNAL-1",
        filled_qty=d("1"),
        stop_price=d("95"),
    )
    assert ok.ok is True

    adapter.fail_protection = True
    bad = sync_protection(
        adapter,
        gate,
        client_order_id="c2",
        symbol="PAPER-INTERNAL-1",
        filled_qty=d("1"),
        stop_price=d("95"),
    )
    assert bad.ok is False
    assert bad.escalate_lock is True
    assert gate.status == AccountStatus.SAFE_LOCK
