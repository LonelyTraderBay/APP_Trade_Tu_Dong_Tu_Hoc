"""T021 — packaged smoke: launch + single-instance.

Exercises the *actual* one-folder PyInstaller build (T020) rather than the
dev entrypoint that `tests/unit/test_desktop_entrypoint.py` and
`tests/unit/test_single_instance.py` cover. The packaged EXE is a slow,
opt-in build artifact — not something every `pytest -m d1c` run should
require — so every test here skips gracefully when it is absent. Build it
first with:

    .venv\\Scripts\\python.exe packaging\\build.py

Contract: specs/003-d1c-desktop-mvp/contracts/packaged-ops.md
  "Second process MUST exit non-zero or focus existing window; MUST NOT
  open second SQLite writer."
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_NAME = "AutoTradeAI"
EXE_PATH = REPO_ROOT / "dist" / APP_NAME / f"{APP_NAME}.exe"

EXIT_OK = 0
EXIT_ALREADY_RUNNING = 3

# The lock is acquired before QApplication is ever built (see
# entrypoints/desktop.py), and offscreen Qt start-up is fast, but give a
# generous ceiling so a slow CI box doesn't flake.
_LOCK_POLL_TIMEOUT_S = 30.0
_LOCK_POLL_INTERVAL_S = 0.5
_PROCESS_TIMEOUT_S = 60

pytestmark = [
    pytest.mark.d1c,
    pytest.mark.skipif(
        not EXE_PATH.exists(),
        reason=(
            f"packaged build not found at {EXE_PATH} — run "
            "packaging/build.py first"
        ),
    ),
]


def _env_for(data_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["AUTOTRADE_DATA_DIR"] = str(data_dir)
    # Never let a packaged-smoke test flash a real window on screen.
    env["QT_QPA_PLATFORM"] = "offscreen"
    return env


def test_check_smoke_starts_and_exits_clean(tmp_path: Path) -> None:
    """`AutoTradeAI.exe --check` must behave like the dev entrypoint: print
    a banner and exit 0 without opening a window, even against a fresh
    (unmigrated) data dir."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    result = subprocess.run(
        [str(EXE_PATH), "--check"],
        capture_output=True,
        text=True,
        env=_env_for(data_dir),
        timeout=_PROCESS_TIMEOUT_S,
    )

    assert result.returncode == EXIT_OK, result.stderr
    assert "autotrade-desktop: ready" in result.stdout


def test_second_instance_is_refused_while_first_holds_the_lock(
    tmp_path: Path,
) -> None:
    """Packaged single-instance guard (contract: packaged-ops.md).

    Launches a real first instance (offscreen, so nothing paints on
    screen) that holds the OS-level lock for the lifetime of its process,
    then repeatedly launches a second `--check` instance until it is
    refused. Any exit other than EXIT_ALREADY_RUNNING while the first
    process is confirmed still alive is a contract violation.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    env = _env_for(data_dir)

    first = subprocess.Popen(
        [str(EXE_PATH)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        # subprocess.Popen() returns as soon as CreateProcess() succeeds —
        # long before the child has actually run far enough to reach
        # guard.acquire(). Without a head start here, the *second* process
        # (spawned synchronously below and thus fully sequential in this
        # process) can occasionally win the mutex race instead, which
        # flips which process gets refused. A short, fixed sleep makes
        # "first" the reliable winner; the polling loop below is then just
        # a safety margin for a slow CI box, not the synchronization
        # mechanism itself.
        time.sleep(1.0)

        second_returncode: int | None = None
        second_stderr = ""
        deadline = time.monotonic() + _LOCK_POLL_TIMEOUT_S
        while time.monotonic() < deadline:
            assert first.poll() is None, (
                "first instance exited early — it must stay alive holding "
                "the single-instance lock for this test to be meaningful"
            )
            second = subprocess.run(
                [str(EXE_PATH), "--check"],
                capture_output=True,
                text=True,
                env=env,
                timeout=_PROCESS_TIMEOUT_S,
            )
            second_returncode = second.returncode
            second_stderr = second.stderr
            if second_returncode == EXIT_ALREADY_RUNNING:
                break
            time.sleep(_LOCK_POLL_INTERVAL_S)

        assert second_returncode == EXIT_ALREADY_RUNNING, (
            f"second instance was never refused (last exit="
            f"{second_returncode}); stderr={second_stderr!r}"
        )
        assert "already running" in second_stderr
    finally:
        # Never leave a packaged EXE running after a test — pass or fail.
        first.terminate()
        try:
            first.wait(timeout=10)
        except subprocess.TimeoutExpired:
            first.kill()
            first.wait(timeout=10)
