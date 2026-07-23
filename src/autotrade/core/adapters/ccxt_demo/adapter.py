"""CCXT DEMO adapter — Binance Spot Testnet allowlist only.

Strategy/Risk/OMS must never import this module's `ccxt` dependency directly.
Tests inject a fake exchange; production builds a sandboxed ccxt.binance client.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import uuid4

from autotrade.core.adapters.ccxt_demo.manifest import CCXT_DEMO_MANIFEST
from autotrade.core.adapters.ccxt_demo.sandbox import assert_demo_sandbox
from autotrade.core.domain.allowlist import (
    D1B_ALLOWLIST,
    AllowlistViolation,
    assert_allowlisted,
)
from autotrade.core.domain.money import d, quantize


@dataclass
class FakeCcxtExchange:
    """In-memory exchange double for contract/fault tests (not real network)."""

    id: str = "binance"
    sandbox: bool = True
    urls: dict[str, Any] = field(
        default_factory=lambda: {"api": {"public": "https://testnet.binance.vision"}}
    )
    fail_auth: bool = False
    timeout_after_send: bool = False
    inject_partial_qty: Decimal | None = None
    disconnect: bool = False
    rate_limited: bool = False
    _orders_by_client: dict[str, dict[str, Any]] = field(default_factory=dict)
    _orders_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    _executions: list[dict[str, Any]] = field(default_factory=list)
    _positions: dict[str, Decimal] = field(default_factory=dict)
    cash: Decimal = field(default_factory=lambda: d("100000"))
    last_price: Decimal = field(default_factory=lambda: d("50000"))
    ohlcv: list[list[Any]] = field(default_factory=list)

    def load_markets(self) -> dict[str, Any]:
        if self.fail_auth:
            raise RuntimeError("auth_failed")
        return {D1B_ALLOWLIST.symbol: {"symbol": D1B_ALLOWLIST.symbol, "spot": True}}

    def create_order(
        self,
        symbol: str,
        type_: str,
        side: str,
        amount: float,
        price: float | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del type_, price
        if self.disconnect:
            raise RuntimeError("network_disconnect")
        if self.rate_limited:
            raise RuntimeError("rate_limit")
        params = params or {}
        client_id = str(params.get("newClientOrderId") or params.get("clientOrderId") or "")
        if client_id and client_id in self._orders_by_client:
            return self._orders_by_client[client_id]
        if self.timeout_after_send:
            # Mark transmission started then raise — caller maps to UNKNOWN
            self.timeout_after_send = False
            raise TimeoutError("timeout_after_send")

        qty = d(str(amount))
        fill_qty = qty
        if self.inject_partial_qty is not None:
            fill_qty = min(qty, self.inject_partial_qty)
        px = self.last_price
        broker_id = f"demo-{uuid4().hex[:12]}"
        order = {
            "id": broker_id,
            "clientOrderId": client_id,
            "symbol": symbol,
            "side": side.lower(),
            "amount": float(qty),
            "filled": float(fill_qty),
            "average": float(px),
            "status": "closed" if fill_qty == qty else "open",
            "fee": {"cost": float(quantize(fill_qty * px * d("0.001"))), "currency": "USDT"},
        }
        if client_id:
            self._orders_by_client[client_id] = order
        self._orders_by_id[broker_id] = order
        exec_id = f"exec-{uuid4().hex[:10]}"
        self._executions.append(
            {
                "id": exec_id,
                "order": broker_id,
                "clientOrderId": client_id,
                "symbol": symbol,
                "side": side.lower(),
                "amount": float(fill_qty),
                "price": float(px),
                "fee": order["fee"],
            }
        )
        if side.lower() == "buy":
            self._positions[symbol] = quantize(self._positions.get(symbol, d("0")) + fill_qty)
            self.cash = quantize(self.cash - fill_qty * px)
        else:
            self._positions[symbol] = quantize(self._positions.get(symbol, d("0")) - fill_qty)
            self.cash = quantize(self.cash + fill_qty * px)
        return order

    def cancel_order(self, order_id: str, symbol: str | None = None) -> dict[str, Any]:
        del symbol
        order = self._orders_by_id.get(order_id)
        if order is None:
            raise RuntimeError("order_not_found")
        order["status"] = "canceled"
        return order

    def fetch_order(self, order_id: str, symbol: str | None = None) -> dict[str, Any]:
        del symbol
        order = self._orders_by_id.get(order_id)
        if order is None:
            raise RuntimeError("order_not_found")
        return order

    def fetch_orders(
        self, symbol: str | None = None, since: Any = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        del since, limit
        orders = list(self._orders_by_id.values())
        if symbol:
            orders = [o for o in orders if o["symbol"] == symbol]
        return orders

    def fetch_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        return [
            o
            for o in self.fetch_orders(symbol=symbol)
            if o.get("status") in {"open", "partially_filled"}
        ]

    def fetch_my_trades(
        self, symbol: str | None = None, since: Any = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        del since, limit
        trades = list(self._executions)
        if symbol:
            trades = [t for t in trades if t["symbol"] == symbol]
        return trades

    def fetch_balance(self) -> dict[str, Any]:
        return {"USDT": {"free": float(self.cash), "total": float(self.cash)}}

    def fetch_positions(self, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        del symbols
        return [
            {"symbol": sym, "contracts": float(qty), "side": "long" if qty > 0 else "flat"}
            for sym, qty in self._positions.items()
        ]

    def fetch_ohlcv(
        self, symbol: str, timeframe: str = "15m", since: Any = None, limit: int | None = None
    ) -> list[list[Any]]:
        del since, limit
        if symbol != D1B_ALLOWLIST.symbol or timeframe != D1B_ALLOWLIST.timeframe:
            raise AllowlistViolation("ohlcv outside allowlist")
        return list(self.ohlcv)


@dataclass
class CcxtDemoAdapter:
    """Broker adapter bound to D1B_ALLOWLIST; inject `exchange` for tests."""

    exchange: Any = None
    endpoint: str = "binance_spot_testnet"
    api_key: str | None = None
    api_secret: str | None = None
    connected: bool = False
    fail_protection: bool = False
    _endpoint_class: str = field(default="", init=False)
    _protections: dict[str, dict[str, Any]] = field(default_factory=dict)

    adapter_id: str = field(default=CCXT_DEMO_MANIFEST.adapter_id, init=False)

    def connect(self) -> None:
        self._endpoint_class = assert_demo_sandbox(self.endpoint)
        assert_allowlisted(
            exchange_id=D1B_ALLOWLIST.exchange_id,
            market=D1B_ALLOWLIST.market,
            endpoint_class=self._endpoint_class,
            symbol=D1B_ALLOWLIST.symbol,
            mode="DEMO",
        )
        if self.exchange is None:
            self.exchange = self._build_real_exchange()
        # Probe
        if hasattr(self.exchange, "load_markets"):
            self.exchange.load_markets()
        self.connected = True

    def _build_real_exchange(self) -> Any:
        import ccxt  # local import — keep ccxt out of Strategy/Risk/OMS graphs

        if not self.api_key or not self.api_secret:
            raise AllowlistViolation("DEMO credentials missing")
        ex = ccxt.binance(
            {
                "apiKey": self.api_key,
                "secret": self.api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }
        )
        if hasattr(ex, "set_sandbox_mode"):
            ex.set_sandbox_mode(True)
        # Re-validate configured URLs stay on testnet class
        api_url = ""
        try:
            api_url = str(ex.urls.get("api", ""))
        except Exception:
            api_url = "binance_spot_testnet"
        assert_demo_sandbox(api_url or "binance_spot_testnet")
        return ex

    def disconnect(self) -> None:
        self.connected = False

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "exchange_id": D1B_ALLOWLIST.exchange_id,
            "modes": list(CCXT_DEMO_MANIFEST.modes),
            "capabilities": list(CCXT_DEMO_MANIFEST.capabilities),
            "endpoint_class": self._endpoint_class or self.endpoint,
            "symbol": D1B_ALLOWLIST.symbol,
            "timeframe": D1B_ALLOWLIST.timeframe,
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
            raise RuntimeError("ccxt demo adapter not connected")
        assert_allowlisted(
            exchange_id=D1B_ALLOWLIST.exchange_id,
            market=D1B_ALLOWLIST.market,
            endpoint_class=self._endpoint_class or assert_demo_sandbox(self.endpoint),
            symbol=symbol,
            mode="DEMO",
        )
        raw = self.exchange.create_order(
            symbol,
            order_type,
            side.lower(),
            float(qty),
            None,
            {"newClientOrderId": client_order_id},
        )
        return self._normalize_order(raw, client_order_id=client_order_id)

    def cancel_order(self, *, broker_order_id: str) -> dict[str, Any]:
        raw = self.exchange.cancel_order(broker_order_id, D1B_ALLOWLIST.symbol)
        return self._normalize_order(raw)

    def query_order_by_client_id(self, client_order_id: str) -> dict[str, Any] | None:
        # Fake path
        if isinstance(self.exchange, FakeCcxtExchange):
            order = self.exchange._orders_by_client.get(client_order_id)
            return self._normalize_order(order, client_order_id=client_order_id) if order else None
        # Real: scan recent orders (testnet)
        try:
            orders = self.exchange.fetch_orders(D1B_ALLOWLIST.symbol, limit=50)
        except Exception:
            return None
        for o in orders:
            if str(o.get("clientOrderId") or "") == client_order_id:
                return self._normalize_order(o, client_order_id=client_order_id)
        return None

    def list_open_orders(self, *, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        opens = self.exchange.fetch_open_orders(D1B_ALLOWLIST.symbol)
        items = [self._normalize_order(o) for o in opens[:page_size]]
        return {
            "items": items,
            "has_more": len(opens) > page_size,
            "done": len(opens) <= page_size,
            "page": page,
            "page_size": page_size,
        }

    def list_executions(
        self, *, cursor: str | None = None, overlap: int = 1
    ) -> dict[str, Any]:
        del cursor, overlap
        trades = self.exchange.fetch_my_trades(D1B_ALLOWLIST.symbol)
        items = [
            {
                "broker_execution_id": str(t.get("id")),
                "broker_order_id": str(t.get("order")),
                "client_order_id": str(t.get("clientOrderId") or ""),
                "symbol": t.get("symbol"),
                "side": t.get("side"),
                "qty": str(t.get("amount") or "0"),
                "price": str(t.get("price") or "0"),
                "fee": str((t.get("fee") or {}).get("cost") or "0"),
            }
            for t in trades
        ]
        return {"items": items, "next_cursor": str(len(items)), "done": True}

    def get_positions(self) -> list[dict[str, Any]]:
        if isinstance(self.exchange, FakeCcxtExchange):
            return [
                {"symbol": s, "qty": str(q)}
                for s, q in self.exchange._positions.items()
                if q != 0
            ]
        raw = self.exchange.fetch_positions([D1B_ALLOWLIST.symbol])
        out: list[dict[str, Any]] = []
        for p in raw or []:
            qty = d(str(p.get("contracts") or p.get("positionAmt") or "0"))
            if qty != 0:
                out.append({"symbol": p.get("symbol") or D1B_ALLOWLIST.symbol, "qty": str(qty)})
        return out

    def get_balances(self) -> dict[str, Any]:
        bal = self.exchange.fetch_balance()
        usdt = bal.get("USDT") or {}
        free = usdt.get("free", usdt.get("total", 0))
        return {"cash": str(free), "currency": "USDT"}

    def fetch_ohlcv_closed(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """Return closed candles only for allowlisted symbol/TF."""
        assert_allowlisted(
            exchange_id=D1B_ALLOWLIST.exchange_id,
            market=D1B_ALLOWLIST.market,
            endpoint_class=self._endpoint_class or assert_demo_sandbox(self.endpoint),
            symbol=D1B_ALLOWLIST.symbol,
            timeframe=D1B_ALLOWLIST.timeframe,
            mode="DEMO",
        )
        rows = self.exchange.fetch_ohlcv(
            D1B_ALLOWLIST.symbol, D1B_ALLOWLIST.timeframe, limit=limit + 1
        )
        # Drop potentially open last candle when using live exchange; fake may set all closed
        if len(rows) > 1 and not isinstance(self.exchange, FakeCcxtExchange):
            closed = rows[:-1]
        else:
            closed = rows
        out: list[dict[str, Any]] = []
        for r in closed:
            out.append(
                {
                    "symbol": D1B_ALLOWLIST.symbol,
                    "timeframe": D1B_ALLOWLIST.timeframe,
                    "open_time_ms": int(r[0]),
                    "open": d(str(r[1])),
                    "high": d(str(r[2])),
                    "low": d(str(r[3])),
                    "close": d(str(r[4])),
                    "volume": d(str(r[5])),
                    "is_closed": True,
                }
            )
        return out

    def upsert_protection(
        self,
        *,
        client_order_id: str,
        symbol: str,
        qty: Decimal,
        stop_price: Decimal,
    ) -> dict[str, Any]:
        if self.fail_protection:
            raise RuntimeError("protection_upsert_failed")
        assert_allowlisted(
            exchange_id=D1B_ALLOWLIST.exchange_id,
            market=D1B_ALLOWLIST.market,
            endpoint_class=self._endpoint_class or assert_demo_sandbox(self.endpoint),
            symbol=symbol,
            mode="DEMO",
        )
        # Spot testnet may lack native OCO; record locally and surface capability honesty
        rec = {
            "client_order_id": client_order_id,
            "symbol": symbol,
            "qty": qty,
            "stop_price": stop_price,
            "status": "LOCAL_BEST_EFFORT",
        }
        self._protections[client_order_id] = rec
        return rec

    @staticmethod
    def _normalize_order(
        raw: dict[str, Any] | None, *, client_order_id: str | None = None
    ) -> dict[str, Any]:
        if raw is None:
            return {}
        filled = d(str(raw.get("filled") or raw.get("amount") or "0"))
        qty = d(str(raw.get("amount") or filled))
        px = d(str(raw.get("average") or raw.get("price") or "0"))
        fee_obj = raw.get("fee") or {}
        fee = d(str(fee_obj.get("cost") or "0"))
        status = str(raw.get("status") or "")
        state = "FILLED" if status in {"closed", "FILLED"} and filled == qty else "PARTIAL"
        if status in {"canceled", "cancelled"}:
            state = "CANCELED"
        return {
            "broker_order_id": str(raw.get("id") or ""),
            "client_order_id": str(raw.get("clientOrderId") or client_order_id or ""),
            "symbol": raw.get("symbol"),
            "side": raw.get("side"),
            "qty": str(qty),
            "filled_qty": str(filled),
            "avg_price": str(px),
            "fee": str(fee),
            "state": state,
            "raw": raw,
        }
