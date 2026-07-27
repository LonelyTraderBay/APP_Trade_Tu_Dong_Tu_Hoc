"""T042 — public, independently-tested flatten helpers.

`flatten_position` / `position_qty` were originally private helpers inside
`autotrade.core.certify.real_lifecycles` (`_flatten` / `_position_qty`).
They are promoted here, unchanged in behavior, so the Kill-switch page's
manual Flatten button (T042) and the DEMO round-trip lifecycle runner
(`run_round_trip_lifecycles`) share one implementation instead of two
private copies drifting apart.

Owner decision 2 (T042): a flatten/close order must be able to proceed even
while the kill-switch is elevated (L1+) — per
`Kien-truc-App-Desktop-Solo-v1.4.md`, L3 is "Cancel entry -> reduce-only
flatten -> reconcile lặp tới flat". `flatten_position` therefore submits
with `reduce_only=True`, which — per the new
`RiskEngine.check_increase(..., reduce_only=...)` flag threaded through
`SubmitRequest` / `DurableSubmitter.submit()` — skips ONLY the
`"kill_switch_blocks_entry"` rejection reason. Every other risk check
(qty limit, notional limit, ...) still applies unchanged; this is a narrow
bypass, not a blanket "skip all risk checks".
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from autotrade.core.adapters.protocol import BrokerAdapter
from autotrade.core.domain.money import d
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest

_FLAT_EPSILON = d("1e-12")


@dataclass(frozen=True, slots=True)
class FlattenResult:
    """Outcome of a flatten attempt — typed, never a bare string.

    `ok=True, qty_closed=0` means "already flat" (a safe no-op, no order
    was submitted). `ok=True, qty_closed>0` means the reported quantity was
    closed. `ok=False` always carries `error`.
    """

    ok: bool
    qty_closed: Decimal | None = None
    error: str | None = None


def position_qty(adapter: BrokerAdapter, symbol: str) -> Decimal:
    """Current open quantity in `symbol` (extracted from
    `real_lifecycles._position_qty`, behavior-identical)."""
    for p in adapter.get_positions():
        if p.get("symbol") == symbol:
            return d(str(p.get("qty") or "0"))
    return d("0")


def flatten_position(
    submitter: DurableSubmitter,
    *,
    account_id: str,
    symbol: str,
    price: Decimal,
) -> FlattenResult:
    """Close the entire open position in `symbol`, if any.

    No-op when already flat. Otherwise submits a single opposite-side,
    `reduce_only=True` order sized to the exact open quantity (extracted
    from `real_lifecycles._flatten`; the only behavior change from that
    private helper is the typed return value and the explicit
    `reduce_only=True` on the submit — see module docstring).
    """
    qty = position_qty(submitter.adapter, symbol)
    if abs(qty) < _FLAT_EPSILON:
        return FlattenResult(ok=True, qty_closed=d("0"))

    side = "sell" if qty > 0 else "buy"
    result = submitter.submit(
        SubmitRequest(
            account_id=account_id,
            symbol=symbol,
            side=side,
            qty=abs(qty),
            price=price,
            reduce_only=True,
        )
    )
    if not result.ok:
        return FlattenResult(ok=False, error=result.error or "flatten_failed")
    return FlattenResult(ok=True, qty_closed=abs(qty))
