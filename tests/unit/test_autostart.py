"""T053 — Windows autostart Run-key toggle.

`winreg` is entirely mocked here via `autotrade.app_ui.services.autostart`'s
module-level guarded import — no real `HKEY_CURRENT_USER` value is ever
touched by this suite, so there is nothing to clean up afterwards. This is
the "mock winreg instead" branch the task brief calls out for exactly this
situation: a fake is simpler and more reliable than proving cleanup of a
real per-user registry value across every test outcome (including a failed
assertion mid-test).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from autotrade.app_ui.services import autostart


class _FakeKey:
    def __enter__(self) -> _FakeKey:
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


class FakeWinreg:
    """Minimal in-memory stand-in for the subset of `winreg` this module uses."""

    HKEY_CURRENT_USER = object()
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def OpenKey(self, hive: object, path: str, reserved: int, access: int) -> _FakeKey:
        assert hive is self.HKEY_CURRENT_USER
        assert path == autostart.RUN_KEY_PATH
        return _FakeKey()

    def QueryValueEx(self, key: _FakeKey, name: str) -> tuple[str, int]:
        if name not in self.values:
            raise FileNotFoundError(name)
        return (self.values[name], self.REG_SZ)

    def SetValueEx(
        self, key: _FakeKey, name: str, reserved: int, value_type: int, value: str
    ) -> None:
        assert value_type == self.REG_SZ
        self.values[name] = value

    def DeleteValue(self, key: _FakeKey, name: str) -> None:
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


@pytest.fixture()
def fake_winreg(monkeypatch: pytest.MonkeyPatch) -> FakeWinreg:
    fake = FakeWinreg()
    monkeypatch.setattr(autostart, "winreg", fake)
    return fake


@pytest.mark.d1c
def test_is_autostart_enabled_false_when_no_value_set(fake_winreg: FakeWinreg) -> None:
    assert autostart.is_autostart_enabled() is False


@pytest.mark.d1c
def test_set_autostart_true_writes_the_run_key_value(fake_winreg: FakeWinreg) -> None:
    autostart.set_autostart(True, exe_path=Path("C:/AutoTradeAI/AutoTradeAI.exe"))

    assert autostart.is_autostart_enabled() is True
    assert fake_winreg.values[autostart.VALUE_NAME] == "C:\\AutoTradeAI\\AutoTradeAI.exe"


@pytest.mark.d1c
def test_set_autostart_false_clears_the_run_key_value(fake_winreg: FakeWinreg) -> None:
    autostart.set_autostart(True, exe_path=Path("C:/AutoTradeAI/AutoTradeAI.exe"))

    autostart.set_autostart(False)

    assert autostart.is_autostart_enabled() is False
    assert autostart.VALUE_NAME not in fake_winreg.values


@pytest.mark.d1c
def test_set_autostart_false_when_never_set_is_a_no_op(fake_winreg: FakeWinreg) -> None:
    autostart.set_autostart(False)  # must not raise

    assert autostart.is_autostart_enabled() is False


@pytest.mark.d1c
def test_set_autostart_scopes_to_exactly_one_named_value(fake_winreg: FakeWinreg) -> None:
    autostart.set_autostart(True, exe_path=Path("C:/AutoTradeAI/AutoTradeAI.exe"))

    assert list(fake_winreg.values.keys()) == [autostart.VALUE_NAME]


@pytest.mark.d1c
def test_default_exe_path_points_at_the_packaged_exe_name() -> None:
    assert autostart.default_exe_path().name == "AutoTradeAI.exe"
