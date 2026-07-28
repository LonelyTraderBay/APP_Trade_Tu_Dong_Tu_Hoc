"""D1b: duplicate / out-of-order executions through the CcxtDemoAdapter path.

`ingest_fill`'s idempotency on (account_id, broker_execution_id) is already
proven generically by tests/fault/test_dup_out_of_order_fills.py, but the D1b
contract's fault-injection table (specs/002-d1b-ccxt-demo/contracts/
ccxt-demo-adapter.md) separately lists "duplicate/out-of-order executions" as
an obligation for *this* adapter. This test exercises the real
CcxtDemoAdapter.list_executions() -> ingest_fill() pipeline (via
autotrade.core.ledger.recon.reconcile, exactly as production recon does) with
a FakeCcxtExchange seeded to deliver executions out of order and with a
duplicate, rather than bypassing the adapter and calling ingest_fill directly.
"""

from __future__ import annotations

import pytest

from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.core.domain.money import d
from autotrade.core.ledger.recon import reconcile
from autotrade.core.oms.account_state import AccountGate
from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.persistence.models import Fill
from autotrade.persistence.uow import UnitOfWork


@pytest.mark.d1b
def test_ccxt_demo_dedupes_duplicate_and_out_of_order_executions(
    migrated_uow: UnitOfWork,
) -> None:
    fake = FakeCcxtExchange()
    adapter = CcxtDemoAdapter(exchange=fake, endpoint="binance_spot_testnet")
    adapter.connect()

    # Seed the fake exchange's trade history directly so we control delivery
    # order: exec-B (the chronologically later fill) is listed BEFORE exec-A
    # (out-of-order), and exec-A is delivered twice (a duplicate/retried
    # execution report) -- both are named obligations in the fault-injection
    # table.
    fake._executions = [
        {
            "id": "exec-B",
            "order": "order-B",
            "clientOrderId": "cid-B",
            "symbol": D1B_ALLOWLIST.symbol,
            "side": "buy",
            "amount": 0.02,
            "price": 51000.0,
            "fee": {"cost": 0.002, "currency": "USDT"},
        },
        {
            "id": "exec-A",
            "order": "order-A",
            "clientOrderId": "cid-A",
            "symbol": D1B_ALLOWLIST.symbol,
            "side": "buy",
            "amount": 0.01,
            "price": 49000.0,
            "fee": {"cost": 0.001, "currency": "USDT"},
        },
        {
            "id": "exec-A",  # duplicate delivery of the same execution
            "order": "order-A",
            "clientOrderId": "cid-A",
            "symbol": D1B_ALLOWLIST.symbol,
            "side": "buy",
            "amount": 0.01,
            "price": 49000.0,
            "fee": {"cost": 0.001, "currency": "USDT"},
        },
    ]

    # Sanity check: the adapter itself does not dedupe or reorder -- it
    # passes the raw execution stream through untouched. Idempotency is the
    # ledger's job, exercised end-to-end below.
    execs = adapter.list_executions()
    assert [item["broker_execution_id"] for item in execs["items"]] == [
        "exec-B",
        "exec-A",
        "exec-A",
    ]

    gate = AccountGate(account_id="demo1")
    gate.mark_ready()
    ks = KillSwitch(scope="account:demo1")

    reconcile(uow=migrated_uow, adapter=adapter, gate=gate, ks=ks, account_id="demo1")

    with migrated_uow.session() as session:
        assert session.query(Fill).count() == 2
        fill_a = session.query(Fill).filter(Fill.broker_execution_id == "exec-A").one()
        fill_b = session.query(Fill).filter(Fill.broker_execution_id == "exec-B").one()
        assert fill_a.qty == d("0.01")
        assert fill_a.price == d("49000")
        assert fill_b.qty == d("0.02")
        assert fill_b.price == d("51000")

    # A second full reconcile pass (e.g. a recon retry after a crash
    # re-fetches the same broker trade history) must not create additional
    # Fill rows -- the pipeline stays idempotent across repeated recon runs,
    # not just within a single batch.
    reconcile(uow=migrated_uow, adapter=adapter, gate=gate, ks=ks, account_id="demo1")

    with migrated_uow.session() as session:
        assert session.query(Fill).count() == 2
