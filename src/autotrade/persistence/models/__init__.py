"""ADR-D03.1 trading tables (no ai_*)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from autotrade.persistence.models.base import Base


class SchemaMeta(Base):
    __tablename__ = "schema_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alembic_version: Mapped[str] = mapped_column(String(64), nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(64))


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class PinVerifier(Base):
    __tablename__ = "pin_verifier"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    salt: Mapped[str] = mapped_column(String(128), nullable=False)
    hash: Mapped[str] = mapped_column(String(256), nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lockout_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Account(Base):
    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    adapter_id: Mapped[str] = mapped_column(String(64), nullable=False, default="paper")
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="PAPER")
    endpoint: Mapped[str | None] = mapped_column(String(256))
    external_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")
    eligibility: Mapped[str] = mapped_column(String(32), nullable=False, default="INELIGIBLE")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AccountSecretsRef(Base):
    __tablename__ = "account_secrets_ref"

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    keyring_service: Mapped[str] = mapped_column(String(128), nullable=False)
    keyring_user: Mapped[str] = mapped_column(String(128), nullable=False)


class InstrumentCache(Base):
    __tablename__ = "instruments_cache"

    internal_symbol: Mapped[str] = mapped_column(String(64), primary_key=True)
    venue_refs: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    tick_size: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False)
    lot_size: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)


class StrategyBinding(Base):
    __tablename__ = "strategy_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    params_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MarketCandle(Base):
    __tablename__ = "market_candles"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "open_time", name="uq_candle_window"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False)
    high: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False)
    low: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False)
    close: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False)
    volume: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feature_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_ref: Mapped[str | None] = mapped_column(String(256))


class Signal(Base):
    __tablename__ = "signals"

    signal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    strength: Mapped[Any | None] = mapped_column(Numeric(24, 12))
    feature_snapshot_id: Mapped[int | None] = mapped_column(Integer)


class RiskCheck(Base):
    __tablename__ = "risk_checks"

    risk_check_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    reasons_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RiskReservation(Base):
    __tablename__ = "risk_reservations"

    reservation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    intent_id: Mapped[str | None] = mapped_column(String(64))
    qty: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False)
    notional: Mapped[Any | None] = mapped_column(Numeric(24, 12))
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="HELD")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrderIntent(Base):
    __tablename__ = "order_intents"

    intent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_order_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    protection_spec: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    risk_check_id: Mapped[str | None] = mapped_column(String(64))
    reservation_id: Mapped[str | None] = mapped_column(String(64))
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    qty: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(128))
    delivery_certainty: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)


class OrderProtection(Base):
    __tablename__ = "order_protection"

    protection_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intent_id: Mapped[str | None] = mapped_column(String(64))
    order_id: Mapped[int | None] = mapped_column(Integer)
    qty: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class Fill(Base):
    __tablename__ = "fills"
    __table_args__ = (
        UniqueConstraint("account_id", "broker_execution_id", name="uq_fill_exec"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_execution_id: Mapped[str] = mapped_column(String(128), nullable=False)
    qty: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False)
    price: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False)
    fee: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False, default=0)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PositionLocal(Base):
    __tablename__ = "positions_local"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    qty: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False)
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class BalanceSnapshot(Base):
    __tablename__ = "balances_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    equity: Mapped[Any] = mapped_column(Numeric(24, 12), nullable=False)
    margin: Mapped[Any | None] = mapped_column(Numeric(24, 12))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)


class ReconBreak(Base):
    __tablename__ = "recon_breaks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class KillSwitchState(Base):
    __tablename__ = "kill_switch_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    triggers_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    latched: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ExecutionCursor(Base):
    __tablename__ = "execution_cursors"

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cursor: Mapped[str] = mapped_column(String(256), nullable=False)
    overlap_policy: Mapped[str] = mapped_column(String(64), nullable=False, default="overlap")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_redacted: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64))


class NotifyOutbox(Base):
    __tablename__ = "notify_outbox"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="telegram")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dead_letter: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload_redacted: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class TelegramUpdate(Base):
    __tablename__ = "telegram_updates"

    update_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(256))


class CertificationRecord(Base):
    """D1b certification evidence for the locked DEMO allowlist tuple."""

    __tablename__ = "certification_records"

    cert_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tuple_key: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    app_version: Mapped[str | None] = mapped_column(String(64))
    ccxt_version: Mapped[str | None] = mapped_column(String(64))
    endpoint_fingerprint: Mapped[str | None] = mapped_column(String(128))
    instrument_metadata_hash: Mapped[str | None] = mapped_column(String(128))
    capability_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    contract_suite_passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fault_suite_passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lifecycle_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lifecycle_passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    soak_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    soak_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    soak_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invalidated_reason: Mapped[str | None] = mapped_column(String(256))


class LifecycleEvidence(Base):
    """Real-testnet completed round-trip lifecycle events (count toward ≥50)."""

    __tablename__ = "lifecycle_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="real_testnet")
    entry_intent_id: Mapped[str | None] = mapped_column(String(64))
    exit_intent_id: Mapped[str | None] = mapped_column(String(64))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(256))


class SoakRun(Base):
    """Wall-clock DEMO soak window metadata."""

    __tablename__ = "soak_runs"

    soak_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unresolved_recon_at_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
