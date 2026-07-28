"""Unit tests for Risk + KS."""

from __future__ import annotations

import pytest

from autotrade.core.domain.money import d
from autotrade.core.risk.engine import RiskEngine, RiskLimits
from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.core.risk.validators import validate_reduce_only


@pytest.mark.d1a
def test_risk_rejects_and_approves() -> None:
    engine = RiskEngine(RiskLimits(max_qty=d("1"), max_notional=d("100")))
    bad = engine.check_increase(account_id="a1", qty=d("2"), price=d("50"))
    assert bad.approved is False
    assert "qty_limit" in bad.reasons

    ok = engine.check_increase(account_id="a1", qty=d("1"), price=d("50"))
    assert ok.approved is True
    assert ok.reservation_id is not None
    assert engine.is_held(ok.reservation_id)


@pytest.mark.d1a
def test_ks_blocks_entry_and_no_auto_downgrade() -> None:
    ks = KillSwitch(scope="account:a1")
    ks.raise_to(3, reason="flatten")
    ks.raise_to(1, reason="should_not_lower")
    assert ks.level == 3

    engine = RiskEngine()
    blocked = engine.check_increase(
        account_id="a1", qty=d("1"), price=d("10"), ks_level=ks.level
    )
    assert blocked.approved is False


@pytest.mark.d1a
def test_check_increase_reduce_only_bypasses_kill_switch_block() -> None:
    """T042 Decision 2 (a): reduce_only=True still submits successfully
    when ks_level >= 1 and other limits pass."""
    engine = RiskEngine(RiskLimits(max_qty=d("10"), max_notional=d("100000")))

    decision = engine.check_increase(
        account_id="a1", qty=d("1"), price=d("50"), ks_level=1, reduce_only=True
    )

    assert decision.approved is True
    assert decision.reservation_id is not None
    assert engine.is_held(decision.reservation_id)
    assert "kill_switch_blocks_entry" not in decision.reasons


@pytest.mark.d1a
def test_check_increase_reduce_only_still_enforces_qty_and_notional_limits() -> None:
    """T042 Decision 2 (b): the bypass is narrow, not a blanket "skip all
    risk checks" — qty/notional limits still reject a reduce_only order."""
    engine = RiskEngine(RiskLimits(max_qty=d("1"), max_notional=d("100")))

    over_qty = engine.check_increase(
        account_id="a1", qty=d("2"), price=d("10"), ks_level=1, reduce_only=True
    )
    assert over_qty.approved is False
    assert "qty_limit" in over_qty.reasons
    assert "kill_switch_blocks_entry" not in over_qty.reasons

    over_notional = engine.check_increase(
        account_id="a1", qty=d("1"), price=d("500"), ks_level=1, reduce_only=True
    )
    assert over_notional.approved is False
    assert "notional_limit" in over_notional.reasons
    assert "kill_switch_blocks_entry" not in over_notional.reasons


@pytest.mark.d1a
def test_check_increase_default_reduce_only_false_still_blocks_on_kill_switch() -> None:
    """T042 Decision 2 (c) — regression guard: reduce_only=False (default,
    i.e. every existing/normal call site) must be rejected on an elevated
    kill-switch exactly as before this task. Do NOT weaken this."""
    engine = RiskEngine(RiskLimits(max_qty=d("10"), max_notional=d("100000")))

    decision = engine.check_increase(account_id="a1", qty=d("1"), price=d("50"), ks_level=1)

    assert decision.approved is False
    assert "kill_switch_blocks_entry" in decision.reasons


@pytest.mark.d1a
def test_reduce_only_validator() -> None:
    assert validate_reduce_only(side="sell", qty=d("1"), position_qty=d("2"))[0] is True
    assert validate_reduce_only(side="sell", qty=d("3"), position_qty=d("2"))[0] is False
    assert validate_reduce_only(side="buy", qty=d("1"), position_qty=d("2"))[0] is False
