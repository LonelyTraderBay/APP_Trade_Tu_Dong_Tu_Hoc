"""Contract tests for PaperAdapter."""

from __future__ import annotations

from decimal import Decimal

import pytest

from autotrade.core.adapters.paper import PaperAdapter
from autotrade.core.domain.money import d


@pytest.fixture()
def paper() -> PaperAdapter:
    adapter = PaperAdapter(last_price=d("100"))
    adapter.connect()
    return adapter


@pytest.mark.d1a
def test_place_full_fill_and_client_id_lookup(paper: PaperAdapter) -> None:
    order = paper.place_order(
        client_order_id="c1",
        symbol="PAPER-INTERNAL-1",
        side="buy",
        qty=d("1"),
    )
    assert order["state"] == "FILLED"
    assert order["filled_qty"] == "1"
    again = paper.place_order(
        client_order_id="c1",
        symbol="PAPER-INTERNAL-1",
        side="buy",
        qty=d("1"),
    )
    assert again["broker_order_id"] == order["broker_order_id"]
    assert paper.query_order_by_client_id("c1") == order


@pytest.mark.d1a
def test_pagination_and_executions(paper: PaperAdapter) -> None:
    for i in range(3):
        paper.place_order(
            client_order_id=f"c{i}",
            symbol="PAPER-INTERNAL-1",
            side="buy",
            qty=d("0.1"),
        )
    page = paper.list_open_orders(page=1, page_size=10)
    assert page["done"] is True
    execs = paper.list_executions(cursor="0", overlap=1)
    assert len(execs["items"]) == 3


@pytest.mark.d1a
def test_injected_partial_and_protection(paper: PaperAdapter) -> None:
    paper.inject_partial_qty = d("0.4")
    order = paper.place_order(
        client_order_id="partial",
        symbol="PAPER-INTERNAL-1",
        side="buy",
        qty=d("1"),
    )
    assert order["state"] == "PARTIAL"
    assert Decimal(order["filled_qty"]) == d("0.4")

    prot = paper.upsert_protection(
        client_order_id="partial",
        symbol="PAPER-INTERNAL-1",
        qty=d("0.4"),
        stop_price=d("95"),
    )
    assert prot["status"] == "ACTIVE"

    paper.fail_protection = True
    with pytest.raises(RuntimeError):
        paper.upsert_protection(
            client_order_id="partial2",
            symbol="PAPER-INTERNAL-1",
            qty=d("0.4"),
            stop_price=d("95"),
        )
