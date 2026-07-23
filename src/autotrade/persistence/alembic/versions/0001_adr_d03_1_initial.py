"""adr_d03_1_initial

Revision ID: 0001_adr_d03_1
Revises:
Create Date: 2026-07-23

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_adr_d03_1"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schema_meta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alembic_version", sa.String(length=64), nullable=False),
        sa.Column("app_version", sa.String(length=64)),
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )
    op.create_table(
        "pin_verifier",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("salt", sa.String(length=128), nullable=False),
        sa.Column("hash", sa.String(length=256), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("lockout_until", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "accounts",
        sa.Column("account_id", sa.String(length=64), primary_key=True),
        sa.Column("adapter_id", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("endpoint", sa.String(length=256)),
        sa.Column("external_id", sa.String(length=128)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("eligibility", sa.String(length=32), nullable=False),
    )
    op.create_table(
        "account_secrets_ref",
        sa.Column("account_id", sa.String(length=64), primary_key=True),
        sa.Column("keyring_service", sa.String(length=128), nullable=False),
        sa.Column("keyring_user", sa.String(length=128), nullable=False),
    )
    op.create_table(
        "instruments_cache",
        sa.Column("internal_symbol", sa.String(length=64), primary_key=True),
        sa.Column("venue_refs", sa.JSON()),
        sa.Column("tick_size", sa.Numeric(24, 12), nullable=False),
        sa.Column("lot_size", sa.Numeric(24, 12), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ttl_seconds", sa.Integer(), nullable=False),
    )
    op.create_table(
        "strategy_bindings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("params_json", sa.JSON()),
        sa.Column("enabled", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "market_candles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(24, 12), nullable=False),
        sa.Column("high", sa.Numeric(24, 12), nullable=False),
        sa.Column("low", sa.Numeric(24, 12), nullable=False),
        sa.Column("close", sa.Numeric(24, 12), nullable=False),
        sa.Column("volume", sa.Numeric(24, 12), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("symbol", "timeframe", "open_time", name="uq_candle_window"),
    )
    op.create_table(
        "feature_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("feature_schema_version", sa.String(length=64), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("payload_hash", sa.String(length=128), nullable=False),
        sa.Column("payload_ref", sa.String(length=256)),
    )
    op.create_table(
        "signals",
        sa.Column("signal_id", sa.String(length=64), primary_key=True),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("strength", sa.Numeric(24, 12)),
        sa.Column("feature_snapshot_id", sa.Integer()),
    )
    op.create_table(
        "risk_checks",
        sa.Column("risk_check_id", sa.String(length=64), primary_key=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("reasons_json", sa.JSON()),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "risk_reservations",
        sa.Column("reservation_id", sa.String(length=64), primary_key=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("intent_id", sa.String(length=64)),
        sa.Column("qty", sa.Numeric(24, 12), nullable=False),
        sa.Column("notional", sa.Numeric(24, 12)),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "order_intents",
        sa.Column("intent_id", sa.String(length=64), primary_key=True),
        sa.Column("client_order_id", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("protection_spec", sa.JSON()),
        sa.Column("risk_check_id", sa.String(length=64)),
        sa.Column("reservation_id", sa.String(length=64)),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("qty", sa.Numeric(24, 12), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("client_order_id"),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("intent_id", sa.String(length=64), nullable=False),
        sa.Column("broker_order_id", sa.String(length=128)),
        sa.Column("delivery_certainty", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
    )
    op.create_table(
        "order_protection",
        sa.Column("protection_id", sa.String(length=64), primary_key=True),
        sa.Column("intent_id", sa.String(length=64)),
        sa.Column("order_id", sa.Integer()),
        sa.Column("qty", sa.Numeric(24, 12), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
    )
    op.create_table(
        "fills",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("broker_execution_id", sa.String(length=128), nullable=False),
        sa.Column("qty", sa.Numeric(24, 12), nullable=False),
        sa.Column("price", sa.Numeric(24, 12), nullable=False),
        sa.Column("fee", sa.Numeric(24, 12), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "broker_execution_id", name="uq_fill_exec"),
    )
    op.create_table(
        "positions_local",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("qty", sa.Numeric(24, 12), nullable=False),
        sa.Column("provenance", sa.JSON()),
    )
    op.create_table(
        "balances_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("equity", sa.Numeric(24, 12), nullable=False),
        sa.Column("margin", sa.Numeric(24, 12)),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
    )
    op.create_table(
        "recon_breaks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON()),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "kill_switch_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("triggers_json", sa.JSON()),
        sa.Column("latched", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "execution_cursors",
        sa.Column("account_id", sa.String(length=64), primary_key=True),
        sa.Column("cursor", sa.String(length=256), nullable=False),
        sa.Column("overlap_policy", sa.String(length=64), nullable=False),
    )
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("payload_redacted", sa.JSON()),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=64)),
    )
    op.create_table(
        "notify_outbox",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt", sa.DateTime(timezone=True)),
        sa.Column("dead_letter", sa.Boolean(), nullable=False),
        sa.Column("payload_redacted", sa.JSON()),
    )
    op.create_table(
        "telegram_updates",
        sa.Column("update_id", sa.Integer(), primary_key=True),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=256)),
    )


def downgrade() -> None:
    for table in (
        "telegram_updates",
        "notify_outbox",
        "audit_events",
        "execution_cursors",
        "kill_switch_state",
        "recon_breaks",
        "balances_snapshots",
        "positions_local",
        "fills",
        "order_protection",
        "orders",
        "order_intents",
        "risk_reservations",
        "risk_checks",
        "signals",
        "feature_snapshots",
        "market_candles",
        "strategy_bindings",
        "instruments_cache",
        "account_secrets_ref",
        "accounts",
        "pin_verifier",
        "app_settings",
        "schema_meta",
    ):
        op.drop_table(table)
