"""D1b contract: list_open_orders pagination beyond one page.

specs/002-d1b-ccxt-demo/contracts/ccxt-demo-adapter.md requires (contract
test obligations: "pagination/cursor"; fault-injection table: "pagination
beyond one page") that `list_open_orders` correctly paginate: a first call
reports `has_more=True`/`done=False` when more orders exist than fit in one
page, and a second page call retrieves the remainder without dropping or
duplicating any order.

FIXED 2026-07-28: `CcxtDemoAdapter.list_open_orders` previously ignored the
`page` keyword argument when slicing (`opens[:page_size]` regardless of
page), so page 2 duplicated page 1 instead of returning the remainder, and
`has_more`/`done` never advanced. This was discovered while writing this
coverage (originally landed as an `xfail(strict=True)` documenting the
defect); the adapter now computes a real `(page - 1) * page_size` offset.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.domain.allowlist import D1B_ALLOWLIST


def _seed_open_orders(adapter: CcxtDemoAdapter, count: int) -> list[str]:
    """Place `count` orders that remain OPEN (partially filled) on the fake
    exchange, and return their broker_order_ids in creation order."""
    ids: list[str] = []
    for i in range(count):
        adapter.exchange.inject_partial_qty = Decimal("0.0001")
        order = adapter.place_order(
            client_order_id=f"cid-{i}",
            symbol=D1B_ALLOWLIST.symbol,
            side="buy",
            qty=Decimal("0.01"),
        )
        assert order["state"] == "PARTIAL"  # i.e. still open on the exchange
        ids.append(order["broker_order_id"])
    return ids


@pytest.mark.d1b
def test_list_open_orders_second_page_retrieves_remainder_without_duplicates() -> None:
    fake = FakeCcxtExchange()
    adapter = CcxtDemoAdapter(exchange=fake, endpoint="binance_spot_testnet")
    adapter.connect()

    order_ids = _seed_open_orders(adapter, count=5)
    assert len(order_ids) == 5

    page_size = 2

    page1 = adapter.list_open_orders(page=1, page_size=page_size)
    assert page1["has_more"] is True
    assert page1["done"] is False
    page1_ids = [item["broker_order_id"] for item in page1["items"]]
    assert page1_ids == order_ids[0:2]

    page2 = adapter.list_open_orders(page=2, page_size=page_size)
    page2_ids = [item["broker_order_id"] for item in page2["items"]]
    # The second page must retrieve the NEXT orders, not repeat page 1.
    assert page2_ids == order_ids[2:4]
    assert set(page2_ids).isdisjoint(page1_ids)
    assert page2["has_more"] is True
    assert page2["done"] is False

    page3 = adapter.list_open_orders(page=3, page_size=page_size)
    page3_ids = [item["broker_order_id"] for item in page3["items"]]
    assert page3_ids == order_ids[4:5]
    assert page3["has_more"] is False
    assert page3["done"] is True

    # Across all pages, every order appears exactly once -- nothing dropped,
    # nothing duplicated.
    all_seen = page1_ids + page2_ids + page3_ids
    assert sorted(all_seen) == sorted(order_ids)
    assert len(all_seen) == len(set(all_seen)) == len(order_ids)
