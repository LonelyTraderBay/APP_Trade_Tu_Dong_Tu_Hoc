"""Strategy binding helpers for DEMO allowlist symbol/TF."""

from __future__ import annotations

from sqlalchemy.orm import Session

from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.persistence.models import StrategyBinding

STRATEGY_ID = "rule_sma_cross_v1"


def bind_demo_strategy(
    session: Session, *, account_id: str, enabled: bool = True
) -> StrategyBinding:
    row = (
        session.query(StrategyBinding)
        .filter_by(account_id=account_id, strategy_id=STRATEGY_ID)
        .one_or_none()
    )
    if row is None:
        row = StrategyBinding(
            strategy_id=STRATEGY_ID,
            account_id=account_id,
            symbol=D1B_ALLOWLIST.symbol,
            timeframe=D1B_ALLOWLIST.timeframe,
            params_json={},
            enabled=enabled,
        )
        session.add(row)
    else:
        row.symbol = D1B_ALLOWLIST.symbol
        row.timeframe = D1B_ALLOWLIST.timeframe
        row.enabled = enabled
        session.add(row)
    return row
