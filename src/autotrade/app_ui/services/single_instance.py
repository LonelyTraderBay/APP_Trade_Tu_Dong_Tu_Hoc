"""T012 — single-instance guard for the desktop app.

Two processes driving one SQLite writer would break the single-writer
invariant (v1.4: "one trading process"), so the desktop refuses to start
twice. Qt-free on purpose: the guard must run before any Qt import, and the
default CI has no PySide6.

Backends:
  * ``mutex`` — Windows named mutex via ``CreateMutexW`` (preferred on Windows).
  * ``file``  — advisory lock on a file under the runtime data dir (fallback,
    and the portable path used off-Windows).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import TracebackType

from autotrade.persistence.engine import runtime_data_dir

#: Exact name pinned by specs/003-d1c-desktop-mvp/data-model.md.
INSTANCE_NAME = "AutoTradeAI.Solo"

_ERROR_ALREADY_EXISTS = 183

#: SQLite-style "pending byte": we lock a byte far past the payload so the
#: owner PID at offset 0 stays readable by the process that lost the race.
#: Locking byte 0 would make the lock file's own diagnostics unreadable.
_LOCK_BYTE_OFFSET = 1024
_PID_FIELD_WIDTH = 32


class AlreadyRunning(RuntimeError):
    """Another AutoTrade desktop instance already holds the lock."""


def _default_lock_path() -> Path:
    return runtime_data_dir() / f"{INSTANCE_NAME}.lock"


class SingleInstanceGuard:
    """Acquire an OS-level exclusive token for this app instance.

    Usage::

        guard = SingleInstanceGuard()
        if not guard.acquire():
            ...  # focus the running window instead of starting a second one
    """

    def __init__(
        self,
        name: str = INSTANCE_NAME,
        *,
        lock_path: Path | None = None,
        backend: str | None = None,
    ) -> None:
        self.name = name
        self._lock_path = lock_path
        self._backend = backend or ("mutex" if sys.platform == "win32" else "file")
        self._handle: int | None = None
        self._fh = None
        self._acquired = False

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def acquired(self) -> bool:
        return self._acquired

    @property
    def lock_path(self) -> Path:
        if self._lock_path is None:
            self._lock_path = _default_lock_path()
        return self._lock_path

    # -- acquisition -----------------------------------------------------

    def acquire(self) -> bool:
        """Return True if this process now owns the instance token."""
        if self._acquired:
            return True
        if self._backend == "mutex":
            self._acquired = self._acquire_mutex()
        else:
            self._acquired = self._acquire_file()
        return self._acquired

    def _acquire_mutex(self) -> bool:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.CreateMutexW(None, True, self.name)
        last_error = ctypes.get_last_error()
        if not handle:
            # Cannot create the mutex at all — fail closed to the file backend
            # rather than silently allowing a second instance.
            self._backend = "file"
            return self._acquire_file()
        if last_error == _ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        return True

    def _acquire_file(self) -> bool:
        path = self.lock_path
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = path.open("a+b")
        try:
            _lock_exclusive(fh)
        except OSError:
            fh.close()
            return False
        fh.seek(0)
        fh.write(str(os.getpid()).encode("ascii").ljust(_PID_FIELD_WIDTH, b" "))
        fh.flush()
        self._fh = fh
        return True

    # -- release ---------------------------------------------------------

    def release(self) -> None:
        if self._handle is not None:
            import ctypes

            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(self._handle)
            self._handle = None
        if self._fh is not None:
            try:
                _unlock(self._fh)
            except OSError:
                pass
            self._fh.close()
            self._fh = None
        self._acquired = False

    # -- context manager --------------------------------------------------

    def __enter__(self) -> SingleInstanceGuard:
        if not self.acquire():
            raise AlreadyRunning(
                f"{self.name} is already running — close the other window first."
            )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()


def read_owner_pid(path: Path | None = None) -> int | None:
    """PID recorded by whoever holds the file lock, for the "already running"
    message. Returns None when the file is absent or unparsable."""
    target = path or _default_lock_path()
    try:
        raw = target.read_bytes()[:_PID_FIELD_WIDTH].strip()
    except OSError:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _lock_exclusive(fh) -> None:  # noqa: ANN001 - binary file object
    if sys.platform == "win32":
        import msvcrt

        fh.seek(_LOCK_BYTE_OFFSET)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(fh) -> None:  # noqa: ANN001 - binary file object
    if sys.platform == "win32":
        import msvcrt

        fh.seek(_LOCK_BYTE_OFFSET)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
