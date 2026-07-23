"""Daily digest payload (Owner local day)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from autotrade.core.notify.compose import compose_message


@dataclass(frozen=True, slots=True)
class DigestInput:
    account_id: str
    mode: str
    pnl: str
    order_count: int
    drawdown: str
    ks_level: int
    adapter_health: str
    as_of: datetime


def build_digest(data: DigestInput) -> dict[str, Any]:
    payload = {
        "pnl": data.pnl,
        "order_count": data.order_count,
        "drawdown": data.drawdown,
        "ks": data.ks_level,
        "adapter_health": data.adapter_health,
        "as_of": data.as_of.isoformat(),
    }
    text = compose_message(
        body=(
            f"Digest ngày: P&L={data.pnl} orders={data.order_count} "
            f"DD={data.drawdown} KS=L{data.ks_level} adapter={data.adapter_health} "
            f"as_of={data.as_of.isoformat()}"
        ),
        mode=data.mode,
        account_id=data.account_id,
        extra=payload,
    )
    return {"text": text, "fields": payload, "mode": data.mode, "account": data.account_id}
