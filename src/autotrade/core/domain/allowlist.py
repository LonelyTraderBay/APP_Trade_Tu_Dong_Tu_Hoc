"""Locked D1b DEMO allowlist tuple (mục 16 / D0-11)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AllowlistTuple:
    """Canonical certified DEMO trading tuple — immutable in D1b."""

    exchange_id: str
    market: str
    endpoint_class: str
    symbol: str
    timeframe: str
    adapter_id: str = "ccxt"
    mode: str = "DEMO"

    @property
    def canonical_key(self) -> str:
        return "|".join(
            [
                self.exchange_id,
                self.market,
                self.endpoint_class,
                self.symbol,
                self.timeframe,
            ]
        )


# Owner-locked 2026-07-23 (D0-11)
D1B_ALLOWLIST = AllowlistTuple(
    exchange_id="binance",
    market="spot",
    endpoint_class="binance_spot_testnet",
    symbol="BTC/USDT",
    timeframe="15m",
)

# Host fragments that identify Binance Spot DEMO/Testnet (refuse production trading hosts).
# Includes legacy testnet.binance.vision and current demo-api.binance.com (ccxt enable_demo_trading).
TESTNET_HOST_MARKERS: frozenset[str] = frozenset(
    {
        "testnet.binance.vision",
        "testnet.binance",
        "binance_spot_testnet",
        "demo-api.binance.com",
        "demo.binance.com",
        "demo-ws-api.binance.com",
        "demo-stream.binance.com",
    }
)

PRODUCTION_HOST_MARKERS: frozenset[str] = frozenset(
    {
        "api.binance.com",
        "api1.binance.com",
        "api2.binance.com",
        "api3.binance.com",
        "api4.binance.com",
    }
)


class AllowlistViolation(ValueError):
    """Raised when a trading request is outside the certified DEMO tuple."""


def assert_allowlisted(
    *,
    exchange_id: str,
    market: str,
    endpoint_class: str,
    symbol: str,
    timeframe: str | None = None,
    mode: str = "DEMO",
) -> None:
    """Fail-closed if any field differs from D1B_ALLOWLIST or mode is LIVE."""
    if mode.upper() == "LIVE":
        raise AllowlistViolation("LIVE mode hard-disabled in D1b")
    if exchange_id != D1B_ALLOWLIST.exchange_id:
        raise AllowlistViolation(f"exchange_id not allowlisted: {exchange_id}")
    if market != D1B_ALLOWLIST.market:
        raise AllowlistViolation(f"market not allowlisted: {market}")
    if endpoint_class != D1B_ALLOWLIST.endpoint_class:
        raise AllowlistViolation(f"endpoint_class not allowlisted: {endpoint_class}")
    if symbol != D1B_ALLOWLIST.symbol:
        raise AllowlistViolation(f"symbol not allowlisted: {symbol}")
    if timeframe is not None and timeframe != D1B_ALLOWLIST.timeframe:
        raise AllowlistViolation(f"timeframe not allowlisted: {timeframe}")
