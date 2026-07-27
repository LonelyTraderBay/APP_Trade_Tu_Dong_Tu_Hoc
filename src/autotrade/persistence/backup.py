"""Pre-migration snapshot via SQLite backup API + integrity_check."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def snapshot_database(src: Path, backup_dir: Path | None = None) -> Path:
    if not src.exists():
        raise FileNotFoundError(src)
    dest_dir = backup_dir or (src.parent / "backups")
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    tmp = dest_dir / f"autotrade-{stamp}.sqlite3.tmp"
    final = dest_dir / f"autotrade-{stamp}.sqlite3"

    # NOTE: `sqlite3.Connection` used as a context manager only commits/rolls
    # back the transaction on `__exit__` — it does NOT close the connection
    # (a well-known stdlib gotcha). On Windows that leaves the temp file
    # handle open, so the `tmp.replace(final)` below intermittently fails
    # with `PermissionError: [WinError 32]`. Close both connections
    # explicitly in `finally` before ever touching the filesystem again.
    source = sqlite3.connect(src)
    dest = sqlite3.connect(tmp)
    try:
        source.backup(dest)
        row = dest.execute("PRAGMA integrity_check").fetchone()
    finally:
        dest.close()
        source.close()

    if not row or row[0] != "ok":
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"integrity_check failed: {row}")

    tmp.replace(final)
    return final
