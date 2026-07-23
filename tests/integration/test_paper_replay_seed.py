"""Seeded Paper replay — bit-for-bit fills/balances."""

from __future__ import annotations

import pytest

from autotrade.core.adapters.paper import PaperAdapter
from autotrade.core.domain.money import d


@pytest.mark.d1a
def test_paper_replay_seed() -> None:
    def run() -> tuple[str, str]:
        a = PaperAdapter(last_price=d("100"), fee_rate=d("0.001"), slippage=d("0.0001"))
        a.connect()
        a.place_order(
            client_order_id="seed-1", symbol="PAPER-INTERNAL-1", side="buy", qty=d("1")
        )
        bal = a.get_balances()["cash"]
        fill = a.list_executions()["items"][0]
        return bal, fill["price"]

    assert run() == run()
