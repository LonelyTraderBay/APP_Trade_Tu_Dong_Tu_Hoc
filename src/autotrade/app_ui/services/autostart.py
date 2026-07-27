"""T053 — Windows autostart (Run-key), Qt-free.

Toggles a single named value under
`HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`
pointing at the packaged `AutoTradeAI.exe`
(`packaging/autotrade-desktop.spec`'s `APP_NAME`). This is per-user, not
systemwide, and touches nothing outside that one named value.

`winreg` is stdlib and Windows-only. The whole app is Windows-only per the
packaging contract, but this module still guards every call with
`sys.platform == "win32"` and no-ops elsewhere so it stays importable (and a
harmless no-op) on a non-Windows CI runner. `winreg` is imported at module
level (guarded) rather than lazily inside each function specifically so
tests can monkeypatch `autotrade.app_ui.services.autostart.winreg` with a
fake object instead of touching the real per-user registry.
"""

from __future__ import annotations

import sys
from pathlib import Path

if sys.platform == "win32":
    import winreg
else:  # pragma: no cover - this app targets Windows only
    winreg = None  # type: ignore[assignment]

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "AutoTradeAI"


def default_exe_path() -> Path:
    """Best-effort path to the packaged `AutoTradeAI.exe` for the Run-key value.

    When running from the frozen PyInstaller build, `sys.executable` already
    *is* AutoTradeAI.exe. In dev/test runs (unpackaged), this falls back to
    the conventional one-folder output path
    `<repo_root>/dist/AutoTradeAI/AutoTradeAI.exe`
    (`packaging/autotrade-desktop.spec`'s `APP_NAME`) even if that build does
    not exist yet — callers that need a guaranteed-existing path should pass
    `exe_path` explicitly to `set_autostart`.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    repo_root = Path(__file__).resolve().parents[4]
    return repo_root / "dist" / "AutoTradeAI" / "AutoTradeAI.exe"


def is_autostart_enabled() -> bool:
    """True if the Run-key value is currently set. Never raises."""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ
        ) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except OSError:
        return False


def set_autostart(enabled: bool, exe_path: Path | None = None) -> None:
    """Set or clear the single `AutoTradeAI` Run-key value.

    No-op on non-Windows. Clearing an already-absent value is not an error
    (mirrors `persistence.secrets.delete_secret`'s "missing is fine" stance).
    """
    if winreg is None:
        return
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
    ) as key:
        if enabled:
            target = exe_path or default_exe_path()
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, str(target))
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except OSError:
                pass
