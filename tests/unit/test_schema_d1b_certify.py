"""D1b schema migration — certify tables + is_active."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

D1B_TABLES = {
    "certification_records",
    "lifecycle_evidence",
    "soak_runs",
}


@pytest.mark.d1b
def test_d1b_certify_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("AUTOTRADE_DATA_DIR", str(data_dir))
    cfg = Config("src/autotrade/persistence/alembic.ini")
    cfg.set_main_option("script_location", str(Path("src/autotrade/persistence/alembic")))
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{(data_dir / 'autotrade.sqlite3').as_posix()}")
    tables = set(inspect(engine).get_table_names())
    assert D1B_TABLES <= tables
    assert not any(t.startswith("ai_") for t in tables)
    cols = {c["name"] for c in inspect(engine).get_columns("accounts")}
    assert "is_active" in cols
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
