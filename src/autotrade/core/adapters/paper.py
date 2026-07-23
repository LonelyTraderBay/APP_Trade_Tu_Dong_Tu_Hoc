"""Deterministic Paper/Fake broker adapter (G2.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import uuid4

from autotrade.core.adapters.manifest import PAPER_MANIFEST
from autotrade.core.domain.money import d, quantize


@dataclass
class PaperAdapter:
    """Happy-path full fills; partial/late only via explicit fault injection."""

    adapter_id: str = PAPER_MANIFEST.adapter_id
    fee_rate: Decimal = field(default_factory=lambda: d("0.001"))
    slippage: Decimal = field(default_factory=lambda: d("0.0001"))
    last_price: Decimal = field(default_factory=lambda: d("100"))
    cash: Decimal = field(default_factory=lambda: d("100000"))
    connected: bool = False
    fail_protection: bool = False
    inject_partial_qty: Decimal | None = None
    _orders_by_client: dict[str, dict[str, Any]] = field(default_factory=dict)
    _orders_by_broker: dict[str, dict[str, Any]] = field(default_factory=dict)
    _executions: list[dict[str, Any]] = field(default_factory=list)
    _positions: dict[str, Decimal] = field(default_factory=dict)
    _protections: dict[str, dict[str, Any]] = field(default_factory=dict)

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "modes": list(PAPER_MANIFEST.modes),
            "capabilities": list(PAPER_MANIFEST.capabilities),
            "connected": self.connected,
        }

    def place_order(
        self,
        *,
        client_order_id: str,
        symbol: str,
        side: str,
        qty: Decimal,
        order_type: str = "market",
    ) -> dict[str, Any]:
        if not self.connected:
            raise RuntimeError("paper adapter not connected")
        existing = self._orders_by_client.get(client_order_id)
        if existing is not None:
            return existing

        fill_qty = qty
        if self.inject_partial_qty is not None:
            fill_qty = min(qty, self.inject_partial_qty)

        px = self.last_price
        if side.lower() == "buy":
            px = quantize(px * (d("1") + self.slippage))
        else:
            px = quantize(px * (d("1") - self.slippage))

        broker_id = f"paper-{uuid4().hex[:12]}"
        fee = quantize(fill_qty * px * self.fee_rate)
        notional = quantize(fill_qty * px)
        if side.lower() == "buy":
            self.cash = quantize(self.cash - notional - fee)
            self._positions[symbol] = quantize(self._positions.get(symbol, d("0")) + fill_qty)
        else:
            self.cash = quantize(self.cash + notional - fee)
            self._positions[symbol] = quantize(self._positions.get(symbol, d("0")) - fill_qty)

        exec_id = f"exec-{uuid4().hex[:12]}"
        order = {
            "client_order_id": client_order_id,
            "broker_order_id": broker_id,
            "symbol": symbol,
            "side": side,
            "qty": str(qty),
            "filled_qty": str(fill_qty),
            "avg_price": str(px),
            "fee": str(fee),
            "order_type": order_type,
            "state": "FILLED" if fill_qty == qty else "PARTIAL",
        }
        self._orders_by_client[client_order_id] = order
        self._orders_by_broker[broker_id] = order
        self._executions.append(
            {
                "broker_execution_id": exec_id,
                "client_order_id": client_order_id,
                "broker_order_id": broker_id,
                "symbol": symbol,
                "qty": str(fill_qty),
                "price": str(px),
                "fee": str(fee),
            }
        )
        return order

    def cancel_order(self, *, broker_order_id: str) -> dict[str, Any]:
        order = self._orders_by_broker.get(broker_order_id)
        if order is None:
            return {"broker_order_id": broker_order_id, "state": "NOT_FOUND"}
        if order["state"] == "FILLED":
            return {**order, "cancel": "TOO_LATE"}
        order = {**order, "state": "CANCELED"}
        self._orders_by_broker[broker_order_id] = order
        self._orders_by_client[order["client_order_id"]] = order
        return order

    def query_order_by_client_id(self, client_order_id: str) -> dict[str, Any] | None:
        return self._orders_by_client.get(client_order_id)

    def list_open_orders(self, *, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        open_orders = [
            o for o in self._orders_by_client.values() if o["state"] in {"PARTIAL", "NEW"}
        ]
        start = (page - 1) * page_size
        chunk = open_orders[start : start + page_size]
        return {
            "page": page,
            "page_size": page_size,
            "total": len(open_orders),
            "items": chunk,
            "done": start + page_size >= len(open_orders),
        }

    def list_executions(
        self, *, cursor: str | None = None, overlap: int = 1
    ) -> dict[str, Any]:
        start = int(cursor or "0")
        start = max(0, start - max(0, overlap))
        items = self._executions[start:]
        next_cursor = str(len(self._executions))
        return {"items": items, "next_cursor": next_cursor, "done": True}

    def get_positions(self) -> list[dict[str, Any]]:
        return [
            {"symbol": sym, "qty": str(qty)}
            for sym, qty in self._positions.items()
            if qty != 0
        ]

    def get_balances(self) -> dict[str, Any]:
        return {"cash": str(self.cash), "currency": "PAPER"}

    def upsert_protection(
        self,
        *,
        client_order_id: str,
        symbol: str,
        qty: Decimal,
        stop_price: Decimal,
    ) -> dict[str, Any]:
        if self.fail_protection:
            raise RuntimeError("protection upsert failed")
        payload = {
            "client_order_id": client_order_id,
            "symbol": symbol,
            "qty": str(qty),
            "stop_price": str(stop_price),
            "status": "ACTIVE",
        }
        self._protections[client_order_id] = payload
        return payload
