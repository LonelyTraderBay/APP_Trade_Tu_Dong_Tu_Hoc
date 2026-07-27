"""T050 — Strategy read model, Qt-free.

Only one strategy exists in this codebase: `rule_sma_cross_v1`
(`autotrade.core.accounts.bindings.STRATEGY_ID`). `StrategyBinding`
(`persistence/models`) already *is* the read model — this module is a thin
query plus the "hard ceiling" values from `D1B_ALLOWLIST`
(`autotrade.core.domain.allowlist`), which the Strategy screen displays as
locked/read-only per `contracts/screens.md` ("rule_sma_cross_v1 params
read-only ceilings"). No mutation lives here, and none should ever be added
— the Strategy page (T050) is explicitly read-only, no editable params.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from autotrade.core.accounts.bindings import STRATEGY_ID
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.persistence.models import StrategyBinding


@dataclass(frozen=True, slots=True)
class StrategyView:
    """Everything the Strategy screen renders, in one immutable read.

    `symbol`/`timeframe`/`params`/`enabled` reflect the persisted
    `StrategyBinding` row when one exists; `binding_found=False` means no
    binding has been created yet (e.g. DEMO was never enabled), in which
    case the allowlist's own symbol/timeframe are shown as the effective
    values `enable_demo` would bind on first use — never a raw "unknown".
    The `ceiling_*` fields are the Owner-locked D1B allowlist tuple itself:
    always present, always immutable, regardless of binding state.
    """

    strategy_id: str
    symbol: str
    timeframe: str
    params: dict[str, Any]
    enabled: bool
    binding_found: bool
    ceiling_exchange_id: str
    ceiling_market: str
    ceiling_endpoint_class: str
    ceiling_symbol: str
    ceiling_timeframe: str


def build_strategy_view(session: Session, *, account_id: str | None = None) -> StrategyView:
    """Assemble the Strategy read model. No mutation, no Qt.

    When `account_id` is given, only that account's binding is considered;
    otherwise the first `rule_sma_cross_v1` binding found is used (today at
    most one DEMO account can be bound per `bind_demo_strategy`).
    """
    query = session.query(StrategyBinding).filter_by(strategy_id=STRATEGY_ID)
    if account_id is not None:
        query = query.filter_by(account_id=account_id)
    binding = query.order_by(StrategyBinding.id).first()

    if binding is None:
        symbol = D1B_ALLOWLIST.symbol
        timeframe = D1B_ALLOWLIST.timeframe
        params: dict[str, Any] = {}
        enabled = False
        binding_found = False
    else:
        symbol = binding.symbol
        timeframe = binding.timeframe
        params = dict(binding.params_json or {})
        enabled = binding.enabled
        binding_found = True

    return StrategyView(
        strategy_id=STRATEGY_ID,
        symbol=symbol,
        timeframe=timeframe,
        params=params,
        enabled=enabled,
        binding_found=binding_found,
        ceiling_exchange_id=D1B_ALLOWLIST.exchange_id,
        ceiling_market=D1B_ALLOWLIST.market,
        ceiling_endpoint_class=D1B_ALLOWLIST.endpoint_class,
        ceiling_symbol=D1B_ALLOWLIST.symbol,
        ceiling_timeframe=D1B_ALLOWLIST.timeframe,
    )
