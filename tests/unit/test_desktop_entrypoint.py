"""T014 — desktop entrypoint wiring and exit codes."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from autotrade.entrypoints import desktop
from autotrade.entrypoints.desktop import (
    EXIT_ALREADY_RUNNING,
    EXIT_NO_UI_EXTRA,
    EXIT_OK,
    main,
)


@pytest.fixture()
def fake_pyside(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    """Satisfy the `import PySide6` gate without installing Qt.

    Lets us exercise the guard / --check branches on a CI box that has no
    optional [ui] extra.
    """
    monkeypatch.setitem(sys.modules, "PySide6", types.ModuleType("PySide6"))
    return None


@pytest.mark.d1c
def test_exit_codes_are_distinct() -> None:
    assert len({EXIT_OK, EXIT_NO_UI_EXTRA, EXIT_ALREADY_RUNNING}) == 3


@pytest.mark.d1c
def test_missing_extra_reports_install_hint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    if "PySide6" in sys.modules:
        pytest.skip("PySide6 installed — skip missing-extra path")
    try:
        import PySide6  # noqa: F401

        pytest.skip("PySide6 installed — skip missing-extra path")
    except ImportError:
        pass

    assert main([]) == EXIT_NO_UI_EXTRA
    err = capsys.readouterr().err
    assert "[ui]" in err
    assert "autotrade-headless" in err


@pytest.mark.d1c
def test_second_instance_is_refused(
    fake_pyside,  # noqa: ANN001
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from autotrade.app_ui.services import single_instance

    monkeypatch.setattr(
        single_instance.SingleInstanceGuard, "acquire", lambda self: False
    )

    assert main(["--check"]) == EXIT_ALREADY_RUNNING
    assert "already running" in capsys.readouterr().err


@pytest.mark.d1c
def test_check_mode_reports_session_and_releases_the_lock(
    fake_pyside,  # noqa: ANN001
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("AUTOTRADE_DATA_DIR", str(data_dir))

    released: list[bool] = []
    from autotrade.app_ui.services import single_instance

    original_release = single_instance.SingleInstanceGuard.release

    def spy_release(self) -> None:  # noqa: ANN001
        released.append(True)
        original_release(self)

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "release", spy_release)

    # No migrations were run: the entrypoint must degrade, not crash.
    assert main(["--check"]) == EXIT_OK
    assert "autotrade-desktop: ready" in capsys.readouterr().out
    assert released == [True]


@pytest.mark.d1c
def test_check_mode_survives_an_unmigrated_database(
    fake_pyside,  # noqa: ANN001
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_dir = tmp_path / "empty"
    data_dir.mkdir()
    monkeypatch.setenv("AUTOTRADE_DATA_DIR", str(data_dir))

    assert main(["--check"]) == EXIT_OK
    assert "session unavailable" in capsys.readouterr().out


@pytest.mark.d1c
def test_entrypoint_module_imports_without_qt() -> None:
    # The module itself must never require PySide6 at import time.
    assert callable(desktop.main)
    assert 'pip install -e ".[ui]"' in desktop._MISSING_UI_MESSAGE
    assert "autotrade-headless" in desktop._MISSING_UI_MESSAGE
