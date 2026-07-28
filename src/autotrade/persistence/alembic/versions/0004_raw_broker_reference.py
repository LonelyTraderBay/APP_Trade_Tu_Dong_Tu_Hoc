"""0004_raw_broker_reference

Revision ID: 0004_raw_broker_reference
Revises: 0003_d1c_ks_intent_ts
Create Date: 2026-07-28

G1.4 (Kien-truc-App-Desktop-Solo-v1.4.md §01): "Lưu venue/market/currency/
contract/position-mode/leg/ticket/raw reference." The adapter-normalized
order dict (which, for `CcxtDemoAdapter`, nests the full underlying ccxt
order payload under `"raw"`) was already computed on every place/cancel
but discarded before persistence. This adds a nullable JSON column so
`Order` rows retain the full (redacted) broker-response reference for
audit/debugging — additive only, no backfill for existing rows (they get
NULL).

`fills` intentionally does NOT get a matching column: at the point
`_finalize_fill` calls `ingest_fill`, the only raw payload available is the
same `order` dict already being written to `orders.raw_reference` — neither
adapter's `list_executions()` exposes a distinct raw per-execution payload
(both adapters normalize execution items down to id/qty/price/fee before
returning them), so a `fills.raw_reference` column would just duplicate the
order-level data already captured.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_raw_broker_reference"
down_revision: str | None = "0003_d1c_ks_intent_ts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("raw_reference", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_column("raw_reference")
