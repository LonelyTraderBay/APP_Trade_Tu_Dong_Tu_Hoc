"""SQLite engine configuration (ADR-D03)."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine


def runtime_data_dir() -> Path:
    """Prefer LOCALAPPDATA/AutoTradeAI; fall back to ./data for tests/dev."""
    override = os.environ.get("AUTOTRADE_DATA_DIR")
    if override:
        path = Path(override)
    else:
        local = os.environ.get("LOCALAPPDATA")
        path = Path(local) / "AutoTradeAI" if local else Path("data")
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_db_path() -> Path:
    return runtime_data_dir() / "autotrade.sqlite3"


def create_sqlite_engine(db_path: Path | None = None, *, echo: bool = False) -> Engine:
    path = db_path or default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{path.as_posix()}"
    engine = create_engine(
        url,
        echo=echo,
        connect_args={"check_same_thread": False, "timeout": 30.0},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=FULL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    # Touch connection so pragmas apply early.
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return engine
