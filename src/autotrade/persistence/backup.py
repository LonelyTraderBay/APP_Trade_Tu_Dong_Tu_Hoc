"""Pre-migration snapshot + restore via SQLite backup API + integrity_check.

FR-005 / `contracts/packaged-ops.md` note on the compatibility check used by
`restore_database` below:

The ORM has a `SchemaMeta` model (`schema_meta` table, columns `id` /
`alembic_version` / `app_version`) that reads as if it were the intended
"is this backup's schema compatible" signal. It is registered with
Alembic's metadata (imported in `alembic/env.py`) and its table is created
by migration `0001_adr_d03_1_initial`, but **no migration and no
application code anywhere in this codebase ever INSERTs a row into it** —
verified by grepping the entire `src/` tree for `SchemaMeta`/`schema_meta`
usage. It is dead schema: always empty in practice. Checking it would make
the restore safety check a no-op against real data.

What actually carries the schema version on disk is Alembic's own
internal `alembic_version` table — a separate, standard table that Alembic
creates and stamps automatically on every `alembic upgrade`, distinct from
the unused `schema_meta`. `restore_database` reads that table directly
(raw `sqlite3`, no SQLAlchemy session) from both the backup file and compares
it against the migration head this running app version ships
(`alembic.script.ScriptDirectory`, reading the bundled `versions/`
scripts — never touches a database). Exact revision equality is required;
a mismatch refuses the restore. This deliberately does not attempt
forward-migration-on-restore — a backup from an older/newer schema is
simply rejected.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_PERSISTENCE_DIR = Path(__file__).resolve().parent


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


@dataclass(frozen=True, slots=True)
class RestoreResult:
    """Outcome of `restore_database`. Never raised — always returned, so a
    caller (the Settings controller) never needs a bare `except Exception`
    around this call to stay safe."""

    ok: bool
    error: str | None = None
    safety_backup_path: Path | None = None


def _integrity_check(path: Path) -> tuple[bool, str]:
    """`PRAGMA integrity_check` against `path`. Never raises — a file that
    is not a SQLite database at all (e.g. garbage bytes) surfaces as a
    normal `(False, <reason>)` result rather than an exception.

    Same Windows-safe connection lifecycle as `snapshot_database`: closed
    explicitly in `finally`, never relying on `sqlite3.Connection` as a
    context manager (that only commits/rolls back, it does not close the
    handle).
    """
    conn = sqlite3.connect(path)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError as exc:
        return False, str(exc)
    finally:
        conn.close()
    ok = bool(row) and row[0] == "ok"
    return ok, (row[0] if row else "no result")


def _read_alembic_version(path: Path) -> str | None:
    """Alembic's own `alembic_version` table — NOT the app's unused
    `schema_meta` (see module docstring). Returns `None` if the table is
    missing (e.g. the file is a valid but non-AutoTrade SQLite database)."""
    conn = sqlite3.connect(path)
    try:
        try:
            row = conn.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
        except sqlite3.OperationalError:
            return None
    finally:
        conn.close()
    return row[0] if row else None


def _expected_alembic_head() -> str | None:
    """The migration head this running app version understands, read from
    the bundled Alembic scripts under `versions/`. Never touches a
    database — this is purely "what does this app's code expect"."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(_PERSISTENCE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_PERSISTENCE_DIR / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def restore_database(
    backup_path: Path,
    target_path: Path,
    *,
    safety_backup_dir: Path | None = None,
) -> RestoreResult:
    """Restore `backup_path` over `target_path`. Never raises.

    Order of operations (each one a hard refusal on failure):
      1. `backup_path` must exist and pass `PRAGMA integrity_check`.
      2. `backup_path`'s Alembic `alembic_version` must exactly equal the
         migration head this app version ships (see module docstring for
         why `alembic_version`, not the dead `schema_meta` table).
      3. `backup_path` is copied into a temp file via the SQLite backup API
         and integrity-checked, mirroring `snapshot_database`'s tmp/final
         dance — connections explicitly closed before any filesystem
         operation. This happens *before* the safety snapshot below on
         purpose: `snapshot_database`'s stamped filenames only have
         1-second resolution and default to the same `backups/` directory
         a restore source file normally lives in, so taking the safety
         snapshot first could, on a same-second collision, silently
         overwrite `backup_path` itself before it's been read (verified
         empirically while building this feature). Capturing it into an
         independent `tmp` file first makes that risk irrelevant.
      4. If `target_path` already exists, a safety snapshot of it is taken
         (`snapshot_database`, into `safety_backup_dir`) — so a bad restore
         is itself recoverable. Skipped (not a failure) when `target_path`
         doesn't exist yet (fresh install).
      5. Committing `tmp` prefers an atomic `Path.replace` (identical to
         `snapshot_database`); if that raises `PermissionError` — which it
         will on Windows whenever `target_path` is held open by another
         connection, e.g. the same running app's own live SQLAlchemy
         engine, since SQLite's Windows VFS does not open files with
         `FILE_SHARE_DELETE` even for an idle, no-transaction connection —
         it falls back to overwriting `target_path`'s *content* in place
         via a second SQLite backup API call (verified empirically to
         succeed with another connection idle-open on the same file)
         rather than swapping the file identity. Restoring from within the
         running app is the expected normal case, not an edge case, so
         this fallback is load-bearing, not defensive dead code.

    Never touches the OS keyring: the SQLite file never held plaintext
    secrets in the first place (only keyring *references* — see
    `persistence.secrets`), so nothing needs to be "restored" there. If the
    restored DB references keyring entries that don't exist on this
    machine, `persistence.secrets.load_secret` already returns `None`
    gracefully — no new handling needed here.
    """
    safety_backup_path: Path | None = None
    try:
        if not backup_path.exists():
            return RestoreResult(ok=False, error=f"backup file not found: {backup_path}")

        ok, detail = _integrity_check(backup_path)
        if not ok:
            return RestoreResult(ok=False, error=f"backup failed integrity_check: {detail}")

        backup_version = _read_alembic_version(backup_path)
        expected_head = _expected_alembic_head()
        if backup_version != expected_head:
            return RestoreResult(
                ok=False,
                error=(
                    f"backup schema version {backup_version!r} does not match "
                    f"the schema this app version expects ({expected_head!r}); "
                    "refusing to restore"
                ),
            )

        # Capture `backup_path`'s content into an independent temp file
        # *before* ever taking the safety snapshot below. This ordering is
        # load-bearing, not stylistic: `snapshot_database`'s stamped
        # filenames only have 1-second resolution, and its default
        # directory is the *same* `backups/` folder a restore source file
        # normally lives in — so a safety snapshot taken first could, on a
        # same-second collision, silently overwrite the very backup file
        # this function is restoring from (verified empirically while
        # building this feature). Reading `backup_path` into `tmp` first
        # means that risk is irrelevant: by the time the safety snapshot
        # runs, the restore source has already been fully captured and
        # integrity-checked independently of anything in `backups/`.
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = target_path.parent / f"{target_path.name}.restore.tmp"

        # Same Windows-safe pattern as `snapshot_database`: explicit
        # `.close()` in `finally`, never a bare `with sqlite3.connect(...)`.
        source = sqlite3.connect(backup_path)
        dest = sqlite3.connect(tmp)
        try:
            source.backup(dest)
            row = dest.execute("PRAGMA integrity_check").fetchone()
        finally:
            dest.close()
            source.close()

        if not row or row[0] != "ok":
            tmp.unlink(missing_ok=True)
            return RestoreResult(
                ok=False,
                error=f"restore copy failed integrity_check: {row}",
                safety_backup_path=safety_backup_path,
            )

        if target_path.exists():
            safety_backup_path = snapshot_database(target_path, safety_backup_dir)

        try:
            tmp.replace(target_path)
        except PermissionError:
            # `target_path` is held open elsewhere (see docstring) — fall
            # back to an in-place content overwrite via the backup API
            # instead of swapping the file identity.
            fallback_source = sqlite3.connect(tmp)
            fallback_dest = sqlite3.connect(target_path)
            try:
                fallback_source.backup(fallback_dest)
                row = fallback_dest.execute("PRAGMA integrity_check").fetchone()
            finally:
                fallback_dest.close()
                fallback_source.close()
            tmp.unlink(missing_ok=True)

            if not row or row[0] != "ok":
                return RestoreResult(
                    ok=False,
                    error=f"restore in-place overwrite failed integrity_check: {row}",
                    safety_backup_path=safety_backup_path,
                )

        return RestoreResult(ok=True, safety_backup_path=safety_backup_path)
    except Exception as exc:  # noqa: BLE001 - contract: restore_database never raises
        return RestoreResult(ok=False, error=str(exc), safety_backup_path=safety_backup_path)
