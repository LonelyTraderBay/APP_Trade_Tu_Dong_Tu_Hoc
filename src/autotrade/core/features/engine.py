"""Versioned feature snapshots from closed candles only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from autotrade.core.market.candles import Candle

FEATURE_SCHEMA_VERSION = "features.sma_atr.v1"


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    feature_schema_version: str
    event_time: datetime
    symbol: str
    sma_fast: Decimal | None
    sma_slow: Decimal | None
    atr: Decimal | None
    payload_hash: str


def _sma(values: list[Decimal], n: int) -> Decimal | None:
    if len(values) < n:
        return None
    window = values[-n:]
    return sum(window, Decimal("0")) / Decimal(n)


def _atr(candles: list[Candle], n: int) -> Decimal | None:
    if len(candles) < n + 1:
        return None
    trs: list[Decimal] = []
    for i in range(1, len(candles)):
        prev_close = candles[i - 1].close
        c = candles[i]
        tr = max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close))
        trs.append(tr)
    if len(trs) < n:
        return None
    window = trs[-n:]
    return sum(window, Decimal("0")) / Decimal(n)


class FeatureEngine:
    def __init__(self, *, schema_version: str = FEATURE_SCHEMA_VERSION) -> None:
        self.schema_version = schema_version

    def snapshot(
        self,
        candles: list[Candle],
        *,
        n_fast: int,
        n_slow: int,
        atr_period: int,
    ) -> FeatureSnapshot | None:
        if not candles or any(not c.is_closed for c in candles):
            return None
        closes = [c.close for c in candles]
        sma_fast = _sma(closes, n_fast)
        sma_slow = _sma(closes, n_slow)
        atr = _atr(candles, atr_period)
        last = candles[-1]
        payload = {
            "schema": self.schema_version,
            "symbol": last.symbol,
            "event_time": last.open_time.isoformat(),
            "sma_fast": None if sma_fast is None else str(sma_fast),
            "sma_slow": None if sma_slow is None else str(sma_slow),
            "atr": None if atr is None else str(atr),
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return FeatureSnapshot(
            feature_schema_version=self.schema_version,
            event_time=last.open_time,
            symbol=last.symbol,
            sma_fast=sma_fast,
            sma_slow=sma_slow,
            atr=atr,
            payload_hash=digest,
        )
