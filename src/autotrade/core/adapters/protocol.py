"""Broker Adapter Interface — venue SDK forbidden in Strategy/Risk/OMS."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BrokerAdapter(Protocol):
    adapter_id: str

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def get_capabilities(self) -> dict[str, Any]: ...

    def place_order(
        self,
        *,
        client_order_id: str,
        symbol: str,
        side: str,
        qty: Decimal,
        order_type: str = "market",
    ) -> dict[str, Any]: ...

    def cancel_order(self, *, broker_order_id: str) -> dict[str, Any]: ...

    def query_order_by_client_id(self, client_order_id: str) -> dict[str, Any] | None: ...

    def list_open_orders(self, *, page: int = 1, page_size: int = 50) -> dict[str, Any]: ...

    def list_executions(
        self, *, cursor: str | None = None, overlap: int = 1
    ) -> dict[str, Any]: ...

    def get_positions(self) -> list[dict[str, Any]]: ...

    def get_balances(self) -> dict[str, Any]: ...

    def upsert_protection(
        self,
        *,
        client_order_id: str,
        symbol: str,
        qty: Decimal,
        stop_price: Decimal,
    ) -> dict[str, Any]: ...
