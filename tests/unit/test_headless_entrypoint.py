"""T015 — headless entrypoint shares the desktop's single-instance lock.

Also covers the FR-009 gap fix: `enable-demo` capturing a real
`cert.capture_baseline` (previously `snapshot_versions` was never called in
production) and the new `cert-check-drift` CLI command.

Also covers the Post-D1a T076 follow-up (2026-07-28): the `run-trading-loop`
CLI wrapper around `core/oms/trading_loop.py::run_trading_loop_iteration`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from autotrade.entrypoints import headless
from autotrade.entrypoints.headless import EXIT_ALREADY_RUNNING, EXIT_DRIFT_DETECTED, main
from autotrade.persistence.models import Account, ReconBreak
from autotrade.persistence.uow import UnitOfWork

PAPER_ACCOUNT_ID = "paper1"
DEMO_ACCOUNT_ID = "demo-binance"


def _seed_paper_active(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add(
            Account(
                account_id=PAPER_ACCOUNT_ID,
                adapter_id="paper",
                mode="PAPER",
                status="READY",
                eligibility="PAPER",
                is_active=True,
            )
        )


def _seed_demo_active(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add(
            Account(
                account_id=DEMO_ACCOUNT_ID,
                adapter_id="ccxt",
                mode="DEMO",
                endpoint="binance_spot_testnet",
                status="READY",
                eligibility="DEMO_CERTIFIED",
                is_active=True,
            )
        )


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


# --- run-trading-loop (Post-D1a T076 follow-up) -----------------------------


@pytest.mark.d1c
def test_run_trading_loop_refuses_without_active_account(
    migrated_uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from autotrade.app_ui.services import single_instance

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", lambda self: True)

    exit_code = main(["run-trading-loop"])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "no active account" in captured.err
    assert "starting PAPER trading loop" not in captured.out


@pytest.mark.d1c
def test_run_trading_loop_refuses_when_active_account_is_not_paper(
    migrated_uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from autotrade.app_ui.services import single_instance

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", lambda self: True)
    _seed_demo_active(migrated_uow)

    exit_code = main(["run-trading-loop"])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "PAPER-only" in captured.err
    assert "DEMO" in captured.err
    assert "starting PAPER trading loop" not in captured.out


@pytest.mark.d1c
def test_run_trading_loop_refuses_when_startup_recovery_locks(
    migrated_uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A locked account (here: an unresolved recon break, same precondition
    `run_desktop_startup_recovery` already enforces for the desktop UI — see
    `tests/unit/test_startup_service.py::test_open_recon_breaks_lock_with_unresolved_breaks_reason`)
    must refuse before the loop ever starts — no adapters/rule constructed,
    no iteration attempted, no submit possible."""
    from autotrade.app_ui.services import single_instance

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", lambda self: True)
    _seed_paper_active(migrated_uow)
    with migrated_uow.session() as session:
        session.add(
            ReconBreak(
                type="orphan",
                payload={"account_id": PAPER_ACCOUNT_ID},
                status="OPEN",
                at=datetime.now(UTC),
            )
        )

    exit_code = main(["run-trading-loop"])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "startup recovery locked" in captured.err
    assert "unresolved_breaks" in captured.err
    assert "starting PAPER trading loop" not in captured.out


@pytest.mark.d1c
def test_run_trading_loop_keyboard_interrupt_exits_cleanly(
    migrated_uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ctrl+C during the inter-poll sleep is a deliberate Owner stop, not a
    failure — must exit 0, not propagate."""
    from autotrade.app_ui.services import single_instance

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", lambda self: True)
    _seed_paper_active(migrated_uow)

    def _raise_on_sleep(seconds: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(headless.time, "sleep", _raise_on_sleep)

    # No --iterations -> would otherwise run forever; the very first
    # inter-poll sleep raises KeyboardInterrupt instead.
    exit_code = main(["run-trading-loop"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "stopped by Owner (Ctrl+C)" in out
    assert "iter=0" in out


@pytest.mark.d1c
def test_run_trading_loop_holds_same_instances_and_evolves_state_across_iterations(
    migrated_uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The single most important invariant from `trading_loop.py`'s own
    contract: `rule`/`market_adapter`/`exec_adapter` must be the SAME
    instances across every poll, never reconstructed. Proven two ways:

    1. Directly — a spy wrapped around the real `run_trading_loop_iteration`
       records `id(market_adapter)`/`id(exec_adapter)`/`id(rule)` on every
       call; all 7 calls must reference the same three objects.
    2. Behaviorally — reuses the exact SC-006 reference series/params from
       `tests/integration/test_trading_loop.py` (n_fast=2, n_slow=4,
       atr_period=2, cooldown=3): a real `ENTER_LONG` cross at the 7th poll
       is only reachable if `_prev_fast`/`_prev_slow` survived from the
       previous polls — a freshly-constructed `RuleSmaCrossV1` every
       iteration would leave `_prev_fast`/`_prev_slow` at `None` forever
       (see `RuleSmaCrossV1.evaluate`'s `if self._prev_fast is not None`
       guard) and no cross could ever fire.
    """
    import autotrade.core.oms.trading_loop as trading_loop_mod
    from autotrade.app_ui.services import single_instance
    from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
    from autotrade.core.domain.allowlist import D1B_ALLOWLIST
    from autotrade.core.strategy import rule_sma_cross_v1 as rule_mod

    monkeypatch.setattr(single_instance.SingleInstanceGuard, "acquire", lambda self: True)
    _seed_paper_active(migrated_uow)

    # Same reference series/params as test_trading_loop.py's SC-006 case:
    # ENTER_LONG fires at index 6 (the 7th poll).
    closes = [10, 9, 8, 7, 6, 7, 8]
    params = rule_mod.StrategyParams(n_fast=2, n_slow=4, atr_period=2, cooldown=3)
    start_ms = 1_700_000_000_000

    def _row(i: int, close: int) -> list[object]:
        ts = start_ms + i * 900_000
        return [ts, close, close + 1, close - 1, close, 10]

    fake = FakeCcxtExchange()
    fake.ohlcv.append(_row(0, closes[0]))
    market_adapter = CcxtDemoAdapter(exchange=fake, endpoint=D1B_ALLOWLIST.endpoint_class)
    monkeypatch.setattr(headless, "_build_loop_market_adapter", lambda: market_adapter)

    # Real RuleSmaCrossV1, just constructed with the small reference-series
    # params instead of production defaults (n_slow=30 would need 30 polls
    # to say anything meaningful in a unit test) — captured via a spy
    # constructor so the test can inspect the SAME instance afterwards.
    created_rules: list[object] = []
    real_rule_cls = rule_mod.RuleSmaCrossV1

    def _small_rule_factory(*_a: object, **_kw: object) -> object:
        rule = real_rule_cls(params)
        created_rules.append(rule)
        return rule

    monkeypatch.setattr(rule_mod, "RuleSmaCrossV1", _small_rule_factory)

    # Feed one new closed candle per inter-poll sleep, so each of the 7
    # iterations sees exactly one genuinely new candle (matching the
    # SC-006 hand-derivation's per-poll cadence).
    remaining = iter(closes[1:])

    def _sleep_and_feed(seconds: float) -> None:
        nxt = next(remaining, None)
        if nxt is not None:
            fake.ohlcv.append(_row(len(fake.ohlcv), nxt))

    monkeypatch.setattr(headless.time, "sleep", _sleep_and_feed)

    real_run_iteration = trading_loop_mod.run_trading_loop_iteration
    calls: list[tuple[int, int, int]] = []

    def _spy_run_iteration(uow, mkt, exe, rule, **kwargs):  # noqa: ANN001, ANN002, ANN003
        calls.append((id(mkt), id(exe), id(rule)))
        return real_run_iteration(uow, mkt, exe, rule, **kwargs)

    monkeypatch.setattr(trading_loop_mod, "run_trading_loop_iteration", _spy_run_iteration)

    exit_code = main(["run-trading-loop", "--iterations", "7"])

    assert exit_code == 0
    out = capsys.readouterr().out
    for i in range(7):
        assert f"iter={i}" in out
    assert "signal=ENTER_LONG" in out
    assert "submit_ok=True" in out
    assert "completed 7 iteration(s)" in out

    # (1) Direct proof: every call referenced the exact same three objects.
    assert len(calls) == 7
    assert len({c[0] for c in calls}) == 1  # market_adapter identity
    assert len({c[1] for c in calls}) == 1  # exec_adapter identity
    assert len({c[2] for c in calls}) == 1  # rule identity
    assert calls[0][0] == id(market_adapter)

    # `rule` was constructed exactly once, not once per iteration.
    assert len(created_rules) == 1
    rule = created_rules[0]

    # (2) Behavioral proof: the real ENTER_LONG cross actually fired, and
    # the rule's in-memory state reflects it — impossible without the
    # SAME instance carrying `_prev_fast`/`_prev_slow`/`_cooldown_left`
    # across every one of the 7 calls above.
    assert rule._in_position is True
    assert rule._prev_fast is not None
    assert rule._prev_slow is not None
