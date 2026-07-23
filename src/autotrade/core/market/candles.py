"""Closed-candle store — open candles must not drive signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Candle:
    symbol: str
    timeframe: str
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    is_closed: bool


@dataclass
class CandleStore:
    _candles: list[Candle] = field(default_factory=list)

    def ingest(self, candle: Candle) -> None:
        self._candles.append(candle)

    def closed_only(self, symbol: str, timeframe: str) -> list[Candle]:
        return [
            c
            for c in self._candles
            if c.symbol == symbol and c.timeframe == timeframe and c.is_closed
        ]
