"""FR-005 — `persistence.backup.restore_database`.

Uses real Alembic migrations (same `command.upgrade(cfg, "head")` idiom as
`tests/conftest.py::migrated_uow`) to build "compatible" backup/target
files instead of hardcoding the current migration head revision string —
that keeps these tests correct even as new migrations are added later.

Never touches a real `%LOCALAPPDATA%\\AutoTradeAI` path: every DB lives
under `tmp_path`, and `AUTOTRADE_DATA_DIR` is monkeypatched before every
`alembic upgrade` invocation.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from autotrade.persistence.backup import (
    DEFAULT_BACKUP_RETENTION,
    list_backups,
    restore_database,
    rotate_backups,
    snapshot_database,
)

_ALEMBIC_INI = Path("src/autotrade/persistence/alembic.ini")
_ALEMBIC_SCRIPTS = Path("src/autotrade/persistence/alembic")

_MARKER_KEY = "restore_test_marker"


@pytest.fixture()
def alembic_cfg() -> Config:
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_ALEMBIC_SCRIPTS))
    return cfg


def _migrated_db(data_dir: Path, monkeypatch: pytest.MonkeyPatch, cfg: Config) -> Path:
    """A real, fully-migrated AutoTrade sqlite file at `data_dir/autotrade.sqlite3`."""
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AUTOTRADE_DATA_DIR", str(data_dir))
    command.upgrade(cfg, "head")
    return data_dir / "autotrade.sqlite3"


def _seed_marker(db_path: Path, value: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)", (_MARKER_KEY, value)
        )
        conn.commit()
    finally:
        conn.close()


def _read_marker(db_path: Path) -> str | None:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (_MARKER_KEY,)
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _integrity_ok(db_path: Path) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    finally:
        conn.close()
    return bool(row) and row[0] == "ok"


# --- refusals ----------------------------------------------------------------


@pytest.mark.d1c
def test_restore_refuses_on_corrupt_backup_file(tmp_path: Path) -> None:
    backup_path = tmp_path / "corrupt.sqlite3"
    backup_path.write_bytes(b"not a sqlite database at all")
    target_path = tmp_path / "target" / "autotrade.sqlite3"

    result = restore_database(backup_path, target_path)

    assert result.ok is False
    assert result.error is not None
    assert result.safety_backup_path is None
    assert not target_path.exists()


@pytest.mark.d1c
def test_restore_refuses_on_missing_backup_file(tmp_path: Path) -> None:
    result = restore_database(tmp_path / "does-not-exist.sqlite3", tmp_path / "target.sqlite3")

    assert result.ok is False
    assert result.error is not None
    assert result.safety_backup_path is None


@pytest.mark.d1c
def test_restore_refuses_on_schema_version_mismatch(tmp_path: Path) -> None:
    """A backup whose `alembic_version` doesn't match this app's migration
    head must be refused — even though it passes `integrity_check` fine."""
    bogus_backup = tmp_path / "bogus.sqlite3"
    conn = sqlite3.connect(bogus_backup)
    try:
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("INSERT INTO alembic_version (version_num) VALUES ('bogus_old_rev')")
        conn.commit()
    finally:
        conn.close()
    target_path = tmp_path / "target" / "autotrade.sqlite3"

    result = restore_database(bogus_backup, target_path)

    assert result.ok is False
    assert result.error is not None
    assert "schema" in result.error.lower()
    assert not target_path.exists()


# --- safety snapshot -----------------------------------------------------------


@pytest.mark.d1c
def test_restore_takes_safety_snapshot_before_overwriting_existing_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, alembic_cfg: Config
) -> None:
    backup_src = _migrated_db(tmp_path / "backupsrc", monkeypatch, alembic_cfg)
    _seed_marker(backup_src, "from_backup")
    backup_file = snapshot_database(backup_src, tmp_path / "backup_store")

    target_db = _migrated_db(tmp_path / "target", monkeypatch, alembic_cfg)
    _seed_marker(target_db, "original_target")

    safety_dir = tmp_path / "safety"
    result = restore_database(backup_file, target_db, safety_backup_dir=safety_dir)

    assert result.ok is True
    assert result.safety_backup_path is not None
    assert result.safety_backup_path.exists()
    assert result.safety_backup_path.parent == safety_dir

    # The safety snapshot must itself be a valid, independently restorable
    # file that preserves the PRE-overwrite content.
    assert _integrity_ok(result.safety_backup_path) is True
    assert _read_marker(result.safety_backup_path) == "original_target"

    # And the live target now holds the restored (backup) content.
    assert _read_marker(target_db) == "from_backup"


@pytest.mark.d1c
def test_restore_with_no_existing_target_skips_safety_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, alembic_cfg: Config
) -> None:
    backup_src = _migrated_db(tmp_path / "backupsrc", monkeypatch, alembic_cfg)
    backup_file = snapshot_database(backup_src, tmp_path / "backup_store")

    target_path = tmp_path / "fresh_install" / "autotrade.sqlite3"
    assert not target_path.exists()
    safety_dir = tmp_path / "safety"

    result = restore_database(backup_file, target_path, safety_backup_dir=safety_dir)

    assert result.ok is True
    assert result.safety_backup_path is None
    assert target_path.exists()
    assert not safety_dir.exists()


# --- end-to-end success ---------------------------------------------------------


@pytest.mark.d1c
def test_restore_succeeds_end_to_end_on_compatible_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, alembic_cfg: Config
) -> None:
    backup_src = _migrated_db(tmp_path / "backupsrc", monkeypatch, alembic_cfg)
    _seed_marker(backup_src, "restored-value")
    backup_file = snapshot_database(backup_src, tmp_path / "backup_store")

    target_db = _migrated_db(tmp_path / "target", monkeypatch, alembic_cfg)

    result = restore_database(backup_file, target_db, safety_backup_dir=tmp_path / "safety")

    assert result.ok is True
    assert result.error is None
    assert _integrity_ok(target_db) is True
    assert _read_marker(target_db) == "restored-value"


@pytest.mark.d1c
def test_restore_succeeds_when_target_is_held_open_by_a_live_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, alembic_cfg: Config
) -> None:
    """The realistic production case: Settings' Restore action runs from
    *inside* the already-running app, which already has a live SQLAlchemy
    engine (idle-pooled connection, no active transaction) open against
    `target_path`. On Windows, SQLite's VFS does not open files with
    `FILE_SHARE_DELETE`, so a plain `Path.replace` onto `target_path` would
    raise `PermissionError` even with no active transaction — confirmed
    empirically before writing the fallback this test exercises.
    `restore_database` must still succeed via its in-place-overwrite
    fallback rather than surfacing that as a failure.
    """
    from autotrade.persistence.engine import create_sqlite_engine

    backup_src = _migrated_db(tmp_path / "backupsrc", monkeypatch, alembic_cfg)
    _seed_marker(backup_src, "restored-value")
    backup_file = snapshot_database(backup_src, tmp_path / "backup_store")

    target_db = _migrated_db(tmp_path / "target", monkeypatch, alembic_cfg)
    _seed_marker(target_db, "original-value")

    # A live engine, exactly like the one `UnitOfWork` wraps in the running
    # app, left idle (no open session/transaction) but still pooling a
    # connection against `target_db`.
    live_engine = create_sqlite_engine(target_db)
    try:
        result = restore_database(backup_file, target_db, safety_backup_dir=tmp_path / "safety")

        assert result.ok is True
        assert result.error is None
        assert result.safety_backup_path is not None
        assert _read_marker(result.safety_backup_path) == "original-value"
        assert _read_marker(target_db) == "restored-value"
        assert _integrity_ok(target_db) is True
    finally:
        live_engine.dispose()


# --- retention rotation (ADR-D03: "giữ mặc định 7 bản") ------------------------


def _make_backup_file(backup_dir: Path, stamp: str) -> Path:
    """A dummy backup file named exactly like `snapshot_database` writes,
    without needing a real sqlite DB — `rotate_backups`/`list_backups` only
    ever look at the filename, never the content, so this is enough to
    exercise rotation without real wall-clock timing between files."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / f"autotrade-{stamp}.sqlite3"
    path.write_bytes(b"not a real sqlite file - only the filename matters here")
    return path


@pytest.mark.d1c
def test_rotate_backups_keeps_newest_n_and_deletes_the_rest(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"
    stamps = [f"2026010{i}T000000Z" for i in range(1, 10)]  # 9 distinct days
    paths = [_make_backup_file(backup_dir, s) for s in stamps]

    deleted = rotate_backups(backup_dir, keep=7)

    assert len(deleted) == 2
    remaining = {p.name for p in backup_dir.iterdir()}
    # the 2 oldest (2026-01-01, 2026-01-02) must be gone
    assert paths[0].name not in remaining
    assert paths[1].name not in remaining
    # the 7 newest must remain
    for p in paths[2:]:
        assert p.name in remaining
    assert len(remaining) == 7


@pytest.mark.d1c
def test_rotate_backups_with_fewer_than_keep_deletes_nothing(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"
    for i in range(1, 4):
        _make_backup_file(backup_dir, f"2026010{i}T000000Z")

    deleted = rotate_backups(backup_dir, keep=7)

    assert deleted == []
    assert len(list(backup_dir.iterdir())) == 3


@pytest.mark.d1c
def test_rotate_backups_ignores_non_backup_files(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True)
    kept_older, kept_newer = (
        _make_backup_file(backup_dir, f"2026010{i}T000000Z") for i in (1, 2)
    )
    tmp_file = backup_dir / "autotrade-20260103T000000Z.sqlite3.tmp"
    tmp_file.write_bytes(b"mid-write, must never be touched")
    unrelated = backup_dir / "notes.txt"
    unrelated.write_text("unrelated file, must never be touched")

    deleted = rotate_backups(backup_dir, keep=1)

    # only 2 real backups exist -> the older one is rotated away, the
    # `.tmp` file and the unrelated file are never candidates at all.
    assert deleted == [kept_older]
    assert not kept_older.exists()
    assert kept_newer.exists()
    assert tmp_file.exists()
    assert unrelated.exists()


@pytest.mark.d1c
def test_rotate_backups_skips_a_file_that_fails_to_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A delete failure on one stale file (permission error, concurrent
    removal, ...) must not raise into the caller and must not prevent the
    other stale files from being cleaned up."""
    backup_dir = tmp_path / "backups"
    stamps = [f"2026010{i}T000000Z" for i in range(1, 4)]
    oldest, middle, newest = (_make_backup_file(backup_dir, s) for s in stamps)

    real_unlink = Path.unlink

    def flaky_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self.name == middle.name:
            raise PermissionError("simulated permission error")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)

    # keep=1 -> both `oldest` and `middle` are stale; `middle` fails to delete.
    deleted = rotate_backups(backup_dir, keep=1)

    assert deleted == [oldest]
    assert not oldest.exists()
    assert middle.exists()  # failed to delete, still there
    assert newest.exists()  # newest, never a rotation candidate


# --- snapshot_database end-to-end rotation --------------------------------------


@pytest.mark.d1c
def test_snapshot_database_triggers_rotation_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, alembic_cfg: Config
) -> None:
    src = _migrated_db(tmp_path / "src", monkeypatch, alembic_cfg)
    backup_dir = tmp_path / "backups"

    for i in range(9):
        moment = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=i)
        snapshot_database(src, backup_dir, now=moment)

    remaining = list_backups(backup_dir)
    assert len(remaining) == DEFAULT_BACKUP_RETENTION == 7
