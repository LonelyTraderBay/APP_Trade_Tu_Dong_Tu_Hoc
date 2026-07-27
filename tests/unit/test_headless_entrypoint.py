"""T015 — headless entrypoint shares the desktop's single-instance lock."""

from __future__ import annotations

import pytest

from autotrade.entrypoints import headless
from autotrade.entrypoints.headless import EXIT_ALREADY_RUNNING, main


@pytest.mark.d1c
def test_second_instance_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Same pattern as test_desktop_entrypoint.test_second_instance_is_refused:
    stub acquire() to simulate the lock already being held by someone else,
    without touching a real system-wide mutex/lock file.
    """
    from autotrade.app_ui.services import single_instance

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", lambda self: False)
    monkeypatch.setattr(single_instance, "read_owner_pid", lambda path=None: 4242)

    assert main([]) == EXIT_ALREADY_RUNNING
    err = capsys.readouterr().err
    assert "already running" in err
    assert "4242" in err


@pytest.mark.d1c
def test_second_instance_message_handles_unknown_owner_pid(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from autotrade.app_ui.services import single_instance

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", lambda self: False)
    monkeypatch.setattr(single_instance, "read_owner_pid", lambda path=None: None)

    assert main(["status"]) == EXIT_ALREADY_RUNNING
    assert "already running" in capsys.readouterr().err


@pytest.mark.d1c
def test_version_bypasses_the_lock(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--version must keep working even while another instance holds the
    lock: it is not a trading action and must never require exclusivity.
    """
    from autotrade import __version__
    from autotrade.app_ui.services import single_instance

    def _fail_if_called(self) -> bool:  # noqa: ANN001
        raise AssertionError("--version must not touch the single-instance guard")

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", _fail_if_called)

    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


@pytest.mark.d1c
def test_lock_is_released_after_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    from autotrade.app_ui.services import single_instance

    released: list[bool] = []
    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", lambda self: True)

    def spy_release(self) -> None:  # noqa: ANN001
        released.append(True)

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "release", spy_release)

    # No subcommand -> the harmless "ready" fallback path; no DB touched.
    assert main([]) == 0
    assert released == [True]


@pytest.mark.d1c
def test_lock_is_released_even_when_dispatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard sits in a try/finally around dispatch, so a subcommand that
    raises must still release the lock rather than leaking it.
    """
    from autotrade.app_ui.services import single_instance

    released: list[bool] = []
    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", lambda self: True)

    def spy_release(self) -> None:  # noqa: ANN001
        released.append(True)

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "release", spy_release)

    def _boom() -> int:
        raise RuntimeError("simulated dispatch failure")

    monkeypatch.setattr(headless, "_status", _boom)

    with pytest.raises(RuntimeError, match="simulated dispatch failure"):
        main(["status"])

    assert released == [True]
