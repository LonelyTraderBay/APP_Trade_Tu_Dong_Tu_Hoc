"""Duplicate / out-of-order executions → unique fill."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from autotrade.core.domain.money import d
from autotrade.core.ledger.fills import ingest_fill
from autotrade.persistence.models import Fill


@pytest.mark.d1a
def test_dup_out_of_order_fills(migrated_uow) -> None:  # noqa: ANN001
    with migrated_uow.session() as session:
        ingest_fill(
            session,
            account_id="paper1",
            broker_execution_id="e1",
            qty=d("1"),
            price=d("100"),
            fee=d("0.1"),
            ts=datetime.now(UTC),
        )
        _, created = ingest_fill(
            session,
            account_id="paper1",
            broker_execution_id="e1",
            qty=d("1"),
            price=d("100"),
            fee=d("0.1"),
            ts=datetime.now(UTC),
        )
        assert created is False
        assert session.query(Fill).count() == 1
