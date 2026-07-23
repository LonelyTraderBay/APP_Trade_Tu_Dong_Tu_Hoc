"""Shared pytest fixtures for D1a."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from autotrade.core.adapters.paper import PaperAdapter
from autotrade.core.domain.money import d
from autotrade.core.oms.account_state import AccountGate
from autotrade.core.risk.engine import RiskEngine
from autotrade.persistence.engine import create_sqlite_engine
from autotrade.persistence.uow import UnitOfWork


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "d1a: D1a exit / fault / integration suites")
    config.addinivalue_line("markers", "d1b: D1b DEMO allowlist / contract / fault / evidence")


@pytest.fixture()
def migrated_uow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> UnitOfWork:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("AUTOTRADE_DATA_DIR", str(data_dir))
    cfg = Config("src/autotrade/persistence/alembic.ini")
    cfg.set_main_option("script_location", str(Path("src/autotrade/persistence/alembic")))
    command.upgrade(cfg, "head")
    engine = create_sqlite_engine(data_dir / "autotrade.sqlite3")
    return UnitOfWork(engine)


@pytest.fixture()
def ready_paper(
    migrated_uow: UnitOfWork,
) -> tuple[UnitOfWork, PaperAdapter, AccountGate, RiskEngine]:
    adapter = PaperAdapter(last_price=d("100"))
    adapter.connect()
    gate = AccountGate(account_id="paper1")
    gate.mark_ready()
    risk = RiskEngine()
    return migrated_uow, adapter, gate, risk
