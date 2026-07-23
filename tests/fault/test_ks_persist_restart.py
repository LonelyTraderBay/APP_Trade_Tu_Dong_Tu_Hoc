"""KS level must survive restart without auto-downgrade."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.persistence.engine import create_sqlite_engine
from autotrade.persistence.uow import UnitOfWork


def test_ks_persist_restart(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("AUTOTRADE_DATA_DIR", str(data_dir))
    cfg = Config("src/autotrade/persistence/alembic.ini")
    cfg.set_main_option("script_location", str(Path("src/autotrade/persistence/alembic")))
    command.upgrade(cfg, "head")

    engine = create_sqlite_engine(data_dir / "autotrade.sqlite3")
    uow = UnitOfWork(engine)
    with uow.session() as session:
        ks = KillSwitch(scope="account:paper1")
        ks.raise_to(2, reason="recon_break")
        ks.persist(session)

    # "Restart": new engine/session, load KS — must remain >= 2.
    engine2 = create_sqlite_engine(data_dir / "autotrade.sqlite3")
    uow2 = UnitOfWork(engine2)
    with uow2.session() as session:
        loaded = KillSwitch.load(session, "account:paper1")
        assert loaded.level == 2
        assert loaded.latched is True
        loaded.raise_to(1, reason="ignored")
        assert loaded.level == 2
