"""0002_d1b_certify_allowlist

Revision ID: 0002_d1b_certify
Revises: 0001_adr_d03_1
Create Date: 2026-07-23

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_d1b_certify"
down_revision: str | None = "0001_adr_d03_1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "certification_records",
        sa.Column("cert_id", sa.String(length=64), primary_key=True),
        sa.Column("tuple_key", sa.String(length=256), nullable=False),
        sa.Column("app_version", sa.String(length=64)),
        sa.Column("ccxt_version", sa.String(length=64)),
        sa.Column("endpoint_fingerprint", sa.String(length=128)),
        sa.Column("instrument_metadata_hash", sa.String(length=128)),
        sa.Column("capability_snapshot_json", sa.JSON()),
        sa.Column("contract_suite_passed_at", sa.DateTime(timezone=True)),
        sa.Column("fault_suite_passed_at", sa.DateTime(timezone=True)),
        sa.Column("lifecycle_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lifecycle_passed_at", sa.DateTime(timezone=True)),
        sa.Column("soak_started_at", sa.DateTime(timezone=True)),
        sa.Column("soak_ended_at", sa.DateTime(timezone=True)),
        sa.Column("soak_passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("invalidated_reason", sa.String(length=256)),
        sa.UniqueConstraint("tuple_key", name="uq_cert_tuple_key"),
    )
    op.create_table(
        "lifecycle_evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("entry_intent_id", sa.String(length=64)),
        sa.Column("exit_intent_id", sa.String(length=64)),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.String(length=256)),
    )
    op.create_table(
        "soak_runs",
        sa.Column("soak_id", sa.String(length=64), primary_key=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("owner_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "unresolved_recon_at_end", sa.Integer(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_table("soak_runs")
    op.drop_table("lifecycle_evidence")
    op.drop_table("certification_records")
    op.drop_column("accounts", "is_active")
