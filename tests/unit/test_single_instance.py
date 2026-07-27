"""T012 — single-instance guard (no Qt required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from autotrade.app_ui.services.single_instance import (
    INSTANCE_NAME,
    AlreadyRunning,
    SingleInstanceGuard,
    read_owner_pid,
)


@pytest.mark.d1c
def test_instance_name_matches_data_model_contract() -> None:
    assert INSTANCE_NAME == "AutoTradeAI.Solo"


@pytest.mark.d1c
def test_file_backend_blocks_second_instance(tmp_path: Path) -> None:
    lock = tmp_path / "AutoTradeAI.Solo.lock"
    first = SingleInstanceGuard(lock_path=lock, backend="file")
    second = SingleInstanceGuard(lock_path=lock, backend="file")

    assert first.acquire() is True
    assert first.acquired is True
    assert second.acquire() is False
    assert second.acquired is False

    first.release()
    assert second.acquire() is True
    second.release()


@pytest.mark.d1c
def test_owner_pid_stays_readable_while_locked(tmp_path: Path) -> None:
    """The loser of the race must be able to name the winner."""
    import os

    lock = tmp_path / "AutoTradeAI.Solo.lock"
    guard = SingleInstanceGuard(lock_path=lock, backend="file")
    assert guard.acquire() is True
    try:
        assert read_owner_pid(lock) == os.getpid()
    finally:
        guard.release()


@pytest.mark.d1c
def test_read_owner_pid_is_none_when_no_lock_file(tmp_path: Path) -> None:
    assert read_owner_pid(tmp_path / "missing.lock") is None


@pytest.mark.d1c
def test_acquire_is_idempotent_for_the_owner(tmp_path: Path) -> None:
    guard = SingleInstanceGuard(lock_path=tmp_path / "x.lock", backend="file")
    assert guard.acquire() is True
    assert guard.acquire() is True
    guard.release()


@pytest.mark.d1c
def test_context_manager_raises_when_already_running(tmp_path: Path) -> None:
    lock = tmp_path / "AutoTradeAI.Solo.lock"
    holder = SingleInstanceGuard(lock_path=lock, backend="file")
    assert holder.acquire() is True
    try:
        with pytest.raises(AlreadyRunning):
            with SingleInstanceGuard(lock_path=lock, backend="file"):
                pass
    finally:
        holder.release()


@pytest.mark.d1c
def test_context_manager_releases_on_exit(tmp_path: Path) -> None:
    lock = tmp_path / "AutoTradeAI.Solo.lock"
    with SingleInstanceGuard(lock_path=lock, backend="file") as guard:
        assert guard.acquired is True
    assert SingleInstanceGuard(lock_path=lock, backend="file").acquire() is True


@pytest.mark.skipif(sys.platform != "win32", reason="named mutex is Windows-only")
@pytest.mark.d1c
def test_windows_mutex_backend_blocks_second_instance() -> None:
    name = "AutoTradeAI.Solo.pytest"
    first = SingleInstanceGuard(name, backend="mutex")
    second = SingleInstanceGuard(name, backend="mutex")

    assert first.acquire() is True
    try:
        assert second.acquire() is False
    finally:
        first.release()
    assert second.acquire() is True
    second.release()


@pytest.mark.d1c
def test_default_backend_is_platform_appropriate() -> None:
    guard = SingleInstanceGuard()
    expected = "mutex" if sys.platform == "win32" else "file"
    assert guard.backend == expected
