"""Continuous recon + execution cursor overlap / orphan detection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from autotrade.core.adapters.protocol import BrokerAdapter
from autotrade.core.domain.money import d
from autotrade.core.ledger.fills import ingest_fill
from autotrade.core.ledger.positions import upsert_position_local
from autotrade.core.oms.account_state import AccountGate
from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.persistence.models import ExecutionCursor, OrderIntent, ReconBreak
from autotrade.persistence.uow import UnitOfWork


def reconcile(
    *,
    uow: UnitOfWork,
    adapter: BrokerAdapter,
    gate: AccountGate,
    ks: KillSwitch,
    account_id: str,
) -> dict[str, Any]:
    broker_positions = {p["symbol"]: d(p["qty"]) for p in adapter.get_positions()}
    breaks: list[str] = []

    with uow.session() as session:
        cursor_row = session.get(ExecutionCursor, account_id)
        cursor = cursor_row.cursor if cursor_row else "0"
        execs = adapter.list_executions(cursor=cursor, overlap=1)
        for item in execs["items"]:
            ingest_fill(
                session,
                account_id=account_id,
                broker_execution_id=item["broker_execution_id"],
                qty=d(item["qty"]),
                price=d(item["price"]),
                fee=d(item["fee"]),
                ts=datetime.now(UTC),
            )
        if cursor_row is None:
            session.add(
                ExecutionCursor(
                    account_id=account_id,
                    cursor=execs["next_cursor"],
                    overlap_policy="overlap",
                )
            )
        else:
            cursor_row.cursor = execs["next_cursor"]

        # Orphan broker position vs no local intent history is a break — broker wins exposure.
        for symbol, qty in broker_positions.items():
            upsert_position_local(
                session,
                account_id=account_id,
                symbol=symbol,
                qty=qty,
                provenance={"source": "broker_recon", "broker_wins": True},
            )
            local_intents = (
                session.query(OrderIntent)
                .filter(
                    OrderIntent.account_id == account_id,
                    OrderIntent.symbol == symbol,
                )
                .count()
            )
            if local_intents == 0 and qty != 0:
                breaks.append(f"orphan_position:{symbol}")
                session.add(
                    ReconBreak(
                        type="orphan_position",
                        payload={"symbol": symbol, "qty": str(qty)},
                        status="open",
                        at=datetime.now(UTC),
                    )
                )

        # Intent/audit history never deleted here.
        if breaks:
            ks.raise_to(2, reason="recon_orphan")
            ks.persist(session)
            gate.lock("recon_orphan")

    return {"breaks": breaks, "broker_positions": {k: str(v) for k, v in broker_positions.items()}}
