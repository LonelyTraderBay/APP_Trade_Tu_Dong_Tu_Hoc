"""Alembic environment for AutoTrade SQLite migrations."""

from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from autotrade.persistence.models import (  # noqa: F401 — register mappers
    Account,
    AccountSecretsRef,
    AppSetting,
    AuditEvent,
    BalanceSnapshot,
    Base,
    ExecutionCursor,
    FeatureSnapshot,
    Fill,
    InstrumentCache,
    KillSwitchState,
    MarketCandle,
    NotifyOutbox,
    Order,
    OrderIntent,
    OrderProtection,
    PinVerifier,
    PositionLocal,
    ReconBreak,
    RiskCheck,
    RiskReservation,
    SchemaMeta,
    Signal,
    StrategyBinding,
    TelegramUpdate,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    override = os.environ.get("AUTOTRADE_DATABASE_URL")
    if override:
        return override
    data_dir = os.environ.get("AUTOTRADE_DATA_DIR")
    if data_dir:
        path = Path(data_dir) / "autotrade.sqlite3"
    else:
        local = os.environ.get("LOCALAPPDATA")
        path = (
            Path(local) / "AutoTradeAI" / "autotrade.sqlite3"
            if local
            else Path("data") / "autotrade.sqlite3"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def run_migrations_offline() -> None:
    url = _url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
