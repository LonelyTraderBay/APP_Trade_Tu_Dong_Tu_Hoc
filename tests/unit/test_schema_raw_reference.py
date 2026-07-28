"""0004 migration — orders.raw_reference (G1.4 raw broker reference)."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from autotrade.persistence import models  # noqa: F401 — registers all tables on Base.metadata
from autotrade.persistence.models.base import Base


@pytest.mark.d1a
def test_orders_raw_reference_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("AUTOTRADE_DATA_DIR", str(data_dir))
    cfg = Config("src/autotrade/persistence/alembic.ini")
    cfg.set_main_option("script_location", str(Path("src/autotrade/persistence/alembic")))
    command.upgrade(cfg, "head")

    migrated_engine = create_engine(f"sqlite:///{(data_dir / 'autotrade.sqlite3').as_posix()}")
    migrated_cols = {c["name"] for c in inspect(migrated_engine).get_columns("orders")}
    assert "raw_reference" in migrated_cols
    with migrated_engine.connect() as conn:
        conn.execute(text("SELECT raw_reference FROM orders"))

    # A DB created straight from ORM metadata (no Alembic) must match what
    # the migration produces on an existing DB — same reasoning as the 0003
    # migration's created_at column.
    fresh_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(fresh_engine)
    fresh_cols = {c["name"] for c in inspect(fresh_engine).get_columns("orders")}
    assert fresh_cols == migrated_cols
