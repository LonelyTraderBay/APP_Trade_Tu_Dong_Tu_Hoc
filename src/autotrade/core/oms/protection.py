"""Order protection attach/update; failure escalates to lock/flatten signal."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from autotrade.core.adapters.paper import PaperAdapter
from autotrade.core.oms.account_state import AccountGate


@dataclass
class ProtectionResult:
    ok: bool
    qty: Decimal | None = None
    error: str | None = None
    escalate_lock: bool = False


def sync_protection(
    adapter: PaperAdapter,
    gate: AccountGate,
    *,
    client_order_id: str,
    symbol: str,
    filled_qty: Decimal,
    stop_price: Decimal,
) -> ProtectionResult:
    try:
        payload = adapter.upsert_protection(
            client_order_id=client_order_id,
            symbol=symbol,
            qty=filled_qty,
            stop_price=stop_price,
        )
        return ProtectionResult(ok=True, qty=Decimal(payload["qty"]))
    except Exception as exc:  # noqa: BLE001 — escalate to safe lock
        gate.lock(f"protection_failed:{exc}")
        return ProtectionResult(
            ok=False, error=str(exc), escalate_lock=True
        )
