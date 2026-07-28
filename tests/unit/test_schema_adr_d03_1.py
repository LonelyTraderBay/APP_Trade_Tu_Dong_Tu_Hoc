"""ADR-D03.1 schema roundtrip — all required tables, no ai_*."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

REQUIRED_TABLES = {
    "schema_meta",
    "app_settings",
    "pin_verifier",
    "accounts",
    "account_secrets_ref",
    "instruments_cache",
    "strategy_bindings",
    "market_candles",
    "feature_snapshots",
    "signals",
    "risk_checks",
    "risk_reservations",
    "order_intents",
    "orders",
    "order_protection",
    "fills",
    "positions_local",
    "balances_snapshots",
    "recon_breaks",
    "kill_switch_state",
    "execution_cursors",
    "audit_events",
    "notify_outbox",
    "telegram_updates",
    "alembic_version",
}


@pytest.fixture()
def migrated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("AUTOTRADE_DATA_DIR", str(data_dir))
    ini = Path("src/autotrade/persistence/alembic.ini")
    cfg = Config(str(ini))
    # Ensure alembic finds scripts relative to ini directory.
    cfg.set_main_option("script_location", str(Path("src/autotrade/persistence/alembic")))
    command.upgrade(cfg, "head")
    return data_dir / "autotrade.sqlite3"


@pytest.mark.d1a
def test_adr_d03_1_tables_exist_and_no_ai(migrated_db: Path) -> None:
    engine = create_engine(f"sqlite:///{migrated_db.as_posix()}")
    tables = set(inspect(engine).get_table_names())
    missing = REQUIRED_TABLES - tables
    assert not missing, f"missing tables: {sorted(missing)}"
    ai_tables = sorted(t for t in tables if t.startswith("ai_"))
    assert ai_tables == []
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() in (0, 1)
