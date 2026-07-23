"""Unit tests for Risk + KS."""

from __future__ import annotations

from autotrade.core.domain.money import d
from autotrade.core.risk.engine import RiskEngine, RiskLimits
from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.core.risk.validators import validate_reduce_only


def test_risk_rejects_and_approves() -> None:
    engine = RiskEngine(RiskLimits(max_qty=d("1"), max_notional=d("100")))
    bad = engine.check_increase(account_id="a1", qty=d("2"), price=d("50"))
    assert bad.approved is False
    assert "qty_limit" in bad.reasons

    ok = engine.check_increase(account_id="a1", qty=d("1"), price=d("50"))
    assert ok.approved is True
    assert ok.reservation_id is not None
    assert engine.is_held(ok.reservation_id)


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


def test_reduce_only_validator() -> None:
    assert validate_reduce_only(side="sell", qty=d("1"), position_qty=d("2"))[0] is True
    assert validate_reduce_only(side="sell", qty=d("3"), position_qty=d("2"))[0] is False
    assert validate_reduce_only(side="buy", qty=d("1"), position_qty=d("2"))[0] is False
