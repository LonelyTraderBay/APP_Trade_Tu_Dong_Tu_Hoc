"""T015 — headless entrypoint shares the desktop's single-instance lock.

Also covers the FR-009 gap fix: `enable-demo` capturing a real
`cert.capture_baseline` (previously `snapshot_versions` was never called in
production) and the new `cert-check-drift` CLI command.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from autotrade.entrypoints import headless
from autotrade.entrypoints.headless import EXIT_ALREADY_RUNNING, EXIT_DRIFT_DETECTED, main


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


def _promote_valid_cert(session) -> None:  # noqa: ANN001
    """Same gate sequence as `test_cert_enable_gates.test_enable_demo_allows_when_all_gates`."""
    from autotrade.core.certify import records as cert
    from autotrade.core.certify.lifecycle import record_completed_lifecycle
    from autotrade.core.certify.soak import SOAK_REQUIRED, SoakController

    cert.mark_contract_passed(session)
    cert.mark_fault_passed(session)
    for i in range(50):
        record_completed_lifecycle(
            session, account_id="demo-binance", source="real_testnet", notes=f"n={i}"
        )
    ctl = SoakController(session=session, account_id="demo-binance")
    run = ctl.start()
    run.started_at = datetime.now(UTC) - SOAK_REQUIRED - timedelta(minutes=1)
    session.add(run)
    ctl.complete(run.soak_id, unresolved_recon=0)
    row = cert.try_promote_valid(session)
    assert row.valid is True


@pytest.mark.d1b
def test_enable_demo_captures_real_baseline_versions(
    migrated_uow,  # noqa: ANN001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-009: `enable-demo` must call `cert.capture_baseline` with real,
    non-placeholder values — before this fix `snapshot_versions` was never
    called anywhere in production, only in tests, so the baseline
    (`app_version`/`ccxt_version`/`endpoint_fingerprint`/
    `instrument_metadata_hash`) never existed for `invalidate_on_change` to
    compare against.
    """
    import ccxt

    from autotrade import __version__ as app_version
    from autotrade.app_ui.services import single_instance
    from autotrade.core.domain.allowlist import D1B_ALLOWLIST
    from autotrade.persistence.models import CertificationRecord

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", lambda self: True)

    with migrated_uow.session() as session:
        _promote_valid_cert(session)

    assert main(["enable-demo", "--account-id", "demo-binance"]) == 0

    with migrated_uow.session() as session:
        row = (
            session.query(CertificationRecord)
            .filter_by(tuple_key=D1B_ALLOWLIST.canonical_key)
            .one()
        )
        assert row.app_version == app_version
        assert row.ccxt_version == ccxt.__version__
        assert row.endpoint_fingerprint == D1B_ALLOWLIST.canonical_key
        assert row.instrument_metadata_hash
        assert len(row.instrument_metadata_hash) == 64  # sha256 hex digest


@pytest.mark.d1b
def test_enable_demo_still_succeeds_when_baseline_capture_fails(
    migrated_uow,  # noqa: ANN001
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Baseline capture is best-effort provenance, not a new gate — a
    failure inside `capture_baseline` must not refuse or crash `enable-demo`
    once the real cert gate has already passed."""
    from autotrade.app_ui.services import single_instance
    from autotrade.core.certify import records as cert

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", lambda self: True)

    def _boom(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise RuntimeError("simulated snapshot failure")

    monkeypatch.setattr(cert, "capture_baseline", _boom)

    with migrated_uow.session() as session:
        _promote_valid_cert(session)

    assert main(["enable-demo", "--account-id", "demo-binance"]) == 0
    assert "cert baseline snapshot skipped" in capsys.readouterr().err


@pytest.mark.d1b
def test_cert_check_drift_no_baseline_yet_is_reported_honestly(
    migrated_uow,  # noqa: ANN001
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A cert row that was never taken through `enable-demo` has no baseline
    to compare against — `invalidate_on_change`'s own guard means nothing
    would ever fire, so this must not be reported as a false "no drift"."""
    from autotrade.app_ui.services import single_instance

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", lambda self: True)

    assert main(["cert-check-drift"]) == 0
    out = capsys.readouterr().out
    assert "no baseline recorded yet" in out
    assert "no drift detected" not in out


@pytest.mark.d1b
def test_cert_check_drift_reports_clean_when_nothing_changed(
    migrated_uow,  # noqa: ANN001
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from autotrade.app_ui.services import single_instance
    from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter
    from autotrade.core.certify import records as cert

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", lambda self: True)

    adapter = CcxtDemoAdapter(endpoint="binance_spot_testnet")
    baseline_values = cert.current_version_snapshot(adapter.get_capabilities())

    with migrated_uow.session() as session:
        cert.snapshot_versions(session, **baseline_values)
        row = cert.ensure_cert_row(session)
        row.valid = True
        session.add(row)

    exit_code = main(["cert-check-drift"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "no drift detected" in out
    assert "cert.valid=True" in out

    with migrated_uow.session() as session:
        row = cert.get_cert(session)
        assert row is not None
        assert row.valid is True


@pytest.mark.d1b
def test_cert_check_drift_detects_change_and_invalidates(
    migrated_uow,  # noqa: ANN001
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from autotrade.app_ui.services import single_instance
    from autotrade.core.certify import records as cert
    from autotrade.core.domain.allowlist import D1B_ALLOWLIST

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", lambda self: True)

    with migrated_uow.session() as session:
        cert.snapshot_versions(
            session,
            app_version="0.0.0-stale",
            ccxt_version="0.0.0-stale",
            endpoint_fingerprint=D1B_ALLOWLIST.canonical_key,
            instrument_metadata_hash="stale-hash",
        )
        row = cert.ensure_cert_row(session)
        row.valid = True
        session.add(row)

    exit_code = main(["cert-check-drift"])

    assert exit_code == EXIT_DRIFT_DETECTED
    out = capsys.readouterr().out
    assert "DRIFT DETECTED" in out
    assert "ccxt_version_changed" in out

    with migrated_uow.session() as session:
        row = cert.get_cert(session)
        assert row is not None
        assert row.valid is False
        assert row.invalidated_reason is not None
        assert "ccxt_version_changed" in row.invalidated_reason
