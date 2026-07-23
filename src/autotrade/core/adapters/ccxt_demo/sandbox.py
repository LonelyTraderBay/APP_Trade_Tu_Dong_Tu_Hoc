"""Binance Spot Testnet sandbox guard — refuse LIVE/production hosts."""

from __future__ import annotations

from urllib.parse import urlparse

from autotrade.core.domain.allowlist import (
    PRODUCTION_HOST_MARKERS,
    TESTNET_HOST_MARKERS,
    AllowlistViolation,
)


def classify_endpoint(url_or_class: str) -> str:
    """Return endpoint_class id or raise if production trading host detected."""
    raw = (url_or_class or "").strip().lower()
    if not raw:
        raise AllowlistViolation("empty endpoint")
    if raw == "binance_spot_testnet" or any(m in raw for m in TESTNET_HOST_MARKERS):
        return "binance_spot_testnet"
    host = raw
    if "://" in raw:
        host = urlparse(raw).hostname or raw
    for marker in PRODUCTION_HOST_MARKERS:
        if marker in host or marker in raw:
            raise AllowlistViolation(f"production endpoint refused: {url_or_class}")
    raise AllowlistViolation(f"unrecognized sandbox endpoint: {url_or_class}")


def assert_demo_sandbox(url_or_class: str) -> str:
    """Validate and return canonical endpoint_class for DEMO trading."""
    return classify_endpoint(url_or_class)
