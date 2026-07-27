"""Headless trading entrypoint (D1a Paper + D1b DEMO CLI).

No localhost HTTP listener — in-process composition only (ADR-D13).

Single-instance (T015, Owner decision): headless shares the exact same
``AutoTradeAI.Solo`` lock as the desktop entrypoint
(``autotrade.app_ui.services.single_instance.SingleInstanceGuard``) — one
shared lock enforces the v1.4 "one trading process" invariant across
desktop + headless together, not just desktop-vs-desktop. Whichever process
(desktop or headless) starts first holds it; the other refuses to start with
a clear stderr message naming the owning PID when available. ``--version``
is exempt — printing the version is not a trading action and must keep
working even while another instance is running.

Exit codes:
  0  success
  1  a run-lifecycles/run-soak invocation completed but failed its gate
  2  operation refused (bad precondition, connection/cert failure, etc.)
  3  another instance already holds the single-instance lock (EXIT_ALREADY_RUNNING)
  4  cert-check-drift detected drift and invalidated the certification
     record (EXIT_DRIFT_DETECTED)

`cancel-intent` reuses exit code 2 (generic refusal) for every failure mode
— unknown intent, wrong state to cancel from, and an adapter-side
CANCEL_UNKNOWN all print a clear reason to stderr and exit 2. A distinct
code was considered and rejected: unlike `run-lifecycles`/`run-soak` (exit 1
for "ran to completion but failed its gate") or `cert-check-drift` (exit 4
for a specific, actionable follow-up), a cancel refusal has no follow-up
action distinct from "read stderr, decide what to do" — so it shares 2 with
every other precondition/refusal case in this file (`switch-account`,
`enable-demo`, ...).
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from typing import Any

EXIT_ALREADY_RUNNING = 3
EXIT_DRIFT_DETECTED = 4


def main(argv: list[str] | None = None) -> int:
    """Run headless entry; D1b DEMO ops + D1a smoke hooks."""
    parser = argparse.ArgumentParser(
        prog="autotrade-headless",
        description="AutoTrade AI headless entry (D1a Paper + D1b DEMO)",
    )
    parser.add_argument("--version", action="store_true", help="Print package version and exit")
    parser.add_argument(
        "--smoke-runtime",
        action="store_true",
        help="Start Runtime OMS command-owner queue, echo one command, exit",
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Send Owner Telegram test message via FakeTelegramSender (dev hook)",
    )

    sub = parser.add_subparsers(dest="cmd")

    p_store = sub.add_parser("demo-store-creds", help="Store DEMO API key/secret in OS keyring")
    p_store.add_argument("--account-id", default="demo-binance")

    sub.add_parser("demo-test-connection", help="Probe Binance Spot Testnet (requires creds)")
    p_en = sub.add_parser("enable-demo", help="Enable DEMO account (requires valid certification)")
    p_en.add_argument("--account-id", default="demo-binance")
    sub.add_parser("disable-demo", help="Deactivate DEMO trading READY")
    p_sw = sub.add_parser("switch-account", help="Switch active account paper|demo")
    p_sw.add_argument("target", choices=["paper", "demo"])
    sub.add_parser("status", help="Print active mode / cert validity (secrets redacted)")

    sub.add_parser("cert-mark-contract", help="Mark DEMO contract suite passed")
    sub.add_parser("cert-mark-fault", help="Mark DEMO fault suite passed")
    sub.add_parser("cert-status", help="Print certification gates (redacted)")
    sub.add_parser(
        "cert-check-drift",
        help="Compare current ccxt/endpoint/instrument/app versions against the "
        "recorded baseline; invalidate cert on drift (FR-009)",
    )
    p_life = sub.add_parser(
        "run-lifecycles",
        help="Run DEMO round-trip lifecycles (requires AUTOTRADE_D1B_REAL=1)",
    )
    p_life.add_argument("--count", type=int, default=None, help="Round-trips (default 50 or env)")
    p_life.add_argument("--account-id", default="demo-binance")
    p_soak = sub.add_parser(
        "run-soak",
        help="Run DEMO continuous soak (requires AUTOTRADE_D1B_REAL=1)",
    )
    p_soak.add_argument("--hours", type=float, default=72.0)
    p_soak.add_argument("--heartbeat-seconds", type=float, default=300.0)
    p_soak.add_argument("--account-id", default="demo-binance")
    sub.add_parser("soak-status", help="Print active/latest soak run")
    p_abort = sub.add_parser("soak-abort", help="Owner-pause active soak (fails continuous gate)")
    p_abort.add_argument("--soak-id", default=None)
    p_abort.add_argument("--account-id", default="demo-binance")
    p_cancel = sub.add_parser(
        "cancel-intent",
        help="Cancel an ACKNOWLEDGED order intent (PAPER or DEMO, by account mode)",
    )
    p_cancel.add_argument("--intent-id", required=True)

    args = parser.parse_args(argv)

    if args.version:
        # Printing the version is not a trading action — it must keep
        # working even while another instance holds the lock, so this
        # branch stays ahead of the guard on purpose.
        from autotrade import __version__

        print(__version__)
        return 0

    # Guard the entire subcommand dispatch: whichever process (desktop or
    # headless) gets here first holds the shared AutoTradeAI.Solo lock, the
    # other refuses to start. Mirrors desktop.py's guard-before-anything-
    # stateful placement.
    from autotrade.app_ui.services.single_instance import (
        SingleInstanceGuard,
        read_owner_pid,
    )

    guard = SingleInstanceGuard()
    if not guard.acquire():
        owner = read_owner_pid(guard.lock_path)
        suffix = "" if owner is None else f" (pid {owner})"
        print(
            f"autotrade-headless: another AutoTrade AI instance is already "
            f"running{suffix} — only one trading process may run at a time.",
            file=sys.stderr,
        )
        return EXIT_ALREADY_RUNNING

    try:
        if args.smoke_runtime:
            return asyncio.run(_smoke_runtime())

        if args.test_telegram:
            from autotrade.core.notify.telegram_transport import (
                FakeTelegramSender,
                TelegramTransport,
            )

            transport = TelegramTransport(sender=FakeTelegramSender(), chat_id="local-dev")
            print(transport.send_test_message())
            return 0

        if args.cmd == "demo-store-creds":
            return _demo_store_creds(args.account_id)
        if args.cmd == "demo-test-connection":
            return _demo_test_connection()
        if args.cmd == "enable-demo":
            return _enable_demo(args.account_id)
        if args.cmd == "disable-demo":
            return _disable_demo()
        if args.cmd == "switch-account":
            return _switch_account(args.target)
        if args.cmd == "status":
            return _status()
        if args.cmd == "cert-mark-contract":
            return _cert_mark("contract")
        if args.cmd == "cert-mark-fault":
            return _cert_mark("fault")
        if args.cmd == "cert-status":
            return _cert_status()
        if args.cmd == "cert-check-drift":
            return _cert_check_drift()
        if args.cmd == "run-lifecycles":
            return _run_lifecycles(account_id=args.account_id, count=args.count)
        if args.cmd == "run-soak":
            return _run_soak(
                account_id=args.account_id,
                hours=args.hours,
                heartbeat_seconds=args.heartbeat_seconds,
            )
        if args.cmd == "soak-status":
            return _soak_status()
        if args.cmd == "soak-abort":
            return _soak_abort(account_id=args.account_id, soak_id=args.soak_id)
        if args.cmd == "cancel-intent":
            return _cancel_intent(args.intent_id)

        print(
            "autotrade-headless: ready (no HTTP). "
            "Use demo-* / cert-* / run-lifecycles / run-soak / switch-account / status.",
            file=sys.stderr,
        )
        return 0
    finally:
        guard.release()


def _uow():
    from autotrade.persistence.engine import create_sqlite_engine
    from autotrade.persistence.uow import UnitOfWork

    return UnitOfWork(create_sqlite_engine())


def _demo_store_creds(account_id: str) -> int:
    from autotrade.persistence.models import Account, AccountSecretsRef
    from autotrade.persistence.secrets import SecretRef, store_secret

    api_key = getpass.getpass("DEMO API key: ")
    api_secret = getpass.getpass("DEMO API secret: ")
    service = "AutoTradeAI"
    user_key = f"{account_id}:api_key"
    user_secret = f"{account_id}:api_secret"
    store_secret(SecretRef(service, user_key), api_key)
    store_secret(SecretRef(service, user_secret), api_secret)
    with _uow().session() as session:
        acc = session.get(Account, account_id)
        if acc is None:
            acc = Account(
                account_id=account_id,
                adapter_id="ccxt",
                mode="DEMO",
                endpoint="binance_spot_testnet",
                status="NEW",
                eligibility="INELIGIBLE",
                is_active=False,
            )
            session.add(acc)
        session.merge(
            AccountSecretsRef(
                account_id=account_id,
                keyring_service=service,
                keyring_user=user_key,
            )
        )
    print("stored (keyring refs only; secrets redacted)")
    return 0


def _load_demo_creds(account_id: str = "demo-binance") -> tuple[str, str]:
    from autotrade.persistence.secrets import SecretRef, load_secret

    service = "AutoTradeAI"
    key = load_secret(SecretRef(service, f"{account_id}:api_key"))
    secret = load_secret(SecretRef(service, f"{account_id}:api_secret"))
    if not key or not secret:
        raise RuntimeError("missing DEMO credentials in keyring")
    return key, secret


def _demo_test_connection() -> int:
    # Prefer fake when no real env — still validates allowlist/sandbox path
    import os

    from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
    from autotrade.core.domain.redaction import redact_mapping

    if os.environ.get("AUTOTRADE_D1B_REAL") == "1":
        key, secret = _load_demo_creds()
        adapter = CcxtDemoAdapter(api_key=key, api_secret=secret, endpoint="binance_spot_testnet")
    else:
        adapter = CcxtDemoAdapter(exchange=FakeCcxtExchange(), endpoint="binance_spot_testnet")
    adapter.connect()
    caps = adapter.get_capabilities()
    print(redact_mapping(caps))
    return 0


def _enable_demo(account_id: str) -> int:
    from autotrade.core.accounts.active import switch_active_account
    from autotrade.core.accounts.bindings import bind_demo_strategy
    from autotrade.core.certify.records import CertificationNotValid, assert_cert_valid_for_trading
    from autotrade.core.oms.account_state import AccountStatus
    from autotrade.persistence.models import Account

    with _uow().session() as session:
        try:
            assert_cert_valid_for_trading(session)
        except CertificationNotValid as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2

        # FR-009 baseline capture — best-effort provenance, not a new gate.
        # The cert gate above already passed; a snapshot failure here must
        # never refuse or crash the enable.
        try:
            from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter
            from autotrade.core.certify.records import capture_baseline

            adapter = CcxtDemoAdapter(endpoint="binance_spot_testnet")
            capture_baseline(session, capability=adapter.get_capabilities())
        except Exception as exc:  # noqa: BLE001 - best-effort, must not block enable
            print(f"cert baseline snapshot skipped: {exc}", file=sys.stderr)

        acc = session.get(Account, account_id)
        if acc is None:
            acc = Account(
                account_id=account_id,
                adapter_id="ccxt",
                mode="DEMO",
                endpoint="binance_spot_testnet",
                status=AccountStatus.READY.value,
                eligibility="DEMO_CERTIFIED",
                is_active=False,
            )
            session.add(acc)
            # This session has autoflush=False, so switch_active_account's
            # session.get(Account, ...) below would not see a pending insert
            # and would raise a spurious SwitchRejected("unknown account").
            session.flush()
        else:
            acc.mode = "DEMO"
            acc.adapter_id = "ccxt"
            acc.status = AccountStatus.READY.value
            acc.eligibility = "DEMO_CERTIFIED"
        bind_demo_strategy(session, account_id=account_id)
        switch_active_account(session, target_account_id=account_id, position_qty=0.0)
    print(f"DEMO enabled account={account_id} mode=DEMO")
    return 0


def _disable_demo() -> int:
    from autotrade.persistence.models import Account

    with _uow().session() as session:
        for acc in session.query(Account).filter_by(mode="DEMO").all():
            acc.status = "SAFE_LOCK"
            acc.is_active = False
            session.add(acc)
    print("DEMO disabled")
    return 0


def _switch_account(target: str) -> int:
    from autotrade.core.accounts.active import SwitchRejected, switch_active_account
    from autotrade.persistence.models import Account

    with _uow().session() as session:
        if target == "paper":
            acc = session.query(Account).filter_by(mode="PAPER").first()
            if acc is None:
                acc = Account(
                    account_id="paper1",
                    adapter_id="paper",
                    mode="PAPER",
                    status="READY",
                    eligibility="PAPER",
                    is_active=False,
                )
                session.add(acc)
                session.flush()
        else:
            acc = session.query(Account).filter_by(mode="DEMO").first()
            if acc is None:
                print("no DEMO account — run demo-store-creds / enable-demo", file=sys.stderr)
                return 2
        try:
            switch_active_account(session, target_account_id=acc.account_id, position_qty=0.0)
        except SwitchRejected as exc:
            print(f"switch refused: {exc}", file=sys.stderr)
            return 2
    print(f"active={target} mode={acc.mode}")
    return 0


def _status() -> int:
    from autotrade.core.accounts.active import get_active_account
    from autotrade.core.certify.records import get_cert
    from autotrade.core.domain.redaction import redact_mapping
    from autotrade.core.notify.compose import compose_message

    with _uow().session() as session:
        active = get_active_account(session)
        cert = get_cert(session)
        mode = active.mode if active else "NONE"
        account_id = active.account_id if active else "none"
        payload: dict[str, Any] = {
            "mode": mode,
            "account_id": account_id,
            "cert_valid": bool(cert.valid) if cert else False,
            "lifecycle_count": cert.lifecycle_count if cert else 0,
            "api_key": "***",
        }
        print(compose_message(body="status", mode=mode, account_id=account_id, extra=payload))
        print(redact_mapping(payload))
    return 0


def _cert_mark(kind: str) -> int:
    from autotrade.core.certify import records as cert_records

    with _uow().session() as session:
        if kind == "contract":
            row = cert_records.mark_contract_passed(session)
        else:
            row = cert_records.mark_fault_passed(session)
        print(
            f"cert-{kind}-marked tuple={row.tuple_key} "
            f"contract={row.contract_suite_passed_at is not None} "
            f"fault={row.fault_suite_passed_at is not None}"
        )
    return 0


def _cert_status() -> int:
    from autotrade.core.certify.records import LIFECYCLE_GATE, get_cert
    from autotrade.core.domain.redaction import redact_mapping

    with _uow().session() as session:
        cert = get_cert(session)
        if cert is None:
            print("cert=none valid=False")
            return 0
        payload = {
            "tuple_key": cert.tuple_key,
            "valid": bool(cert.valid),
            "lifecycle_count": int(cert.lifecycle_count or 0),
            "lifecycle_gate": LIFECYCLE_GATE,
            "soak_passed": bool(cert.soak_passed),
            "contract_passed": cert.contract_suite_passed_at is not None,
            "fault_passed": cert.fault_suite_passed_at is not None,
            "invalidated_reason": cert.invalidated_reason,
            "api_key": "***",
        }
        print(redact_mapping(payload))
    return 0


def _cert_check_drift() -> int:
    """FR-009 drift check: compare current ccxt/endpoint/instrument/app
    versions against the baseline recorded by `cert.capture_baseline`
    (established the first time `enable-demo` succeeds) and invalidate the
    certification record if anything drifted. Owner-schedulable (cron/Task
    Scheduler) via `EXIT_DRIFT_DETECTED`.

    Note on `invalidate_on_change`'s `reason` argument: an empty string is
    passed deliberately (verified against `core/certify/invalidate.py`) —
    a *non-empty* `reason` makes that function invalidate unconditionally
    (`if detected or reason:`), which would report drift on every single
    invocation, even a completely clean one. An empty reason makes the
    actual invalidation depend purely on a detected mismatch, which is what
    a drift *check* is supposed to do.

    The `detected` list below mirrors `invalidate_on_change`'s own
    field-by-field comparison, recomputed here only for accurate reporting —
    reading `cert.invalidated_reason` back after the call is not enough on
    its own, since that field can already be non-empty/valid=False for a
    reason unrelated to this run (e.g. gates re-run and failed since the
    baseline was captured), which would make an unqualified read misreport
    "drift" on a clean run.
    """
    from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter
    from autotrade.core.certify import records as cert_records
    from autotrade.core.certify.invalidate import invalidate_on_change

    with _uow().session() as session:
        baseline = cert_records.get_cert(session)
        if baseline is None or not baseline.ccxt_version:
            print(
                "cert-check-drift: no baseline recorded yet "
                "(enable DEMO at least once to establish one)"
            )
            return 0

        adapter = CcxtDemoAdapter(endpoint="binance_spot_testnet")
        current = cert_records.current_version_snapshot(adapter.get_capabilities())

        detected: list[str] = []
        if baseline.ccxt_version and current["ccxt_version"] != baseline.ccxt_version:
            detected.append("ccxt_version_changed")
        if (
            baseline.endpoint_fingerprint
            and current["endpoint_fingerprint"] != baseline.endpoint_fingerprint
        ):
            detected.append("endpoint_fingerprint_changed")
        if (
            baseline.instrument_metadata_hash
            and current["instrument_metadata_hash"] != baseline.instrument_metadata_hash
        ):
            detected.append("instrument_metadata_changed")
        if baseline.app_version and current["app_version"] != baseline.app_version:
            detected.append("app_version_changed")

        invalidate_on_change(
            session,
            reason="",
            current_ccxt=current["ccxt_version"],
            current_endpoint_fp=current["endpoint_fingerprint"],
            current_instrument_hash=current["instrument_metadata_hash"],
            current_app=current["app_version"],
        )
        row = cert_records.get_cert(session)
        valid = bool(row.valid) if row else False

    if detected:
        print(
            f"cert-check-drift: DRIFT DETECTED cert.valid={valid} "
            f"reasons={'+'.join(detected)}"
        )
        return EXIT_DRIFT_DETECTED

    print(f"cert-check-drift: no drift detected, cert.valid={valid}")
    return 0


def _run_lifecycles(*, account_id: str, count: int | None) -> int:
    from autotrade.core.certify.real_lifecycles import (
        build_real_adapter,
        lifecycle_count_from_env,
        require_real_env,
        run_round_trip_lifecycles,
    )

    try:
        require_real_env()
        adapter = build_real_adapter(account_id=account_id)
        adapter.connect()
        n = count if count is not None else lifecycle_count_from_env(50)
        result = run_round_trip_lifecycles(
            uow=_uow(),
            adapter=adapter,
            account_id=account_id,
            count=n,
            source="real_testnet",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"run-lifecycles failed: {exc}", file=sys.stderr)
        return 2
    print(
        f"lifecycles completed={result.completed}/{result.requested} "
        f"total_real={result.total_real_count} errors={result.errors}"
    )
    return 0 if result.completed == result.requested and not result.errors else 1


def _run_soak(*, account_id: str, hours: float, heartbeat_seconds: float) -> int:
    from autotrade.core.certify.real_lifecycles import build_real_adapter, require_real_env
    from autotrade.core.certify.real_soak import run_soak
    from autotrade.core.certify.soak import SOAK_REQUIRED

    write_cert = hours >= (SOAK_REQUIRED.total_seconds() / 3600.0)
    try:
        require_real_env()
        adapter = build_real_adapter(account_id=account_id)
        adapter.connect()
        result = run_soak(
            uow=_uow(),
            adapter=adapter,
            account_id=account_id,
            hours=hours,
            heartbeat_seconds=heartbeat_seconds,
            write_cert=write_cert,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"run-soak failed: {exc}", file=sys.stderr)
        return 2
    print(
        f"soak id={result.soak_id} passed={result.passed} "
        f"elapsed={result.elapsed} unresolved={result.unresolved_recon} "
        f"msg={result.message} write_cert={write_cert}"
    )
    return 0 if result.passed else 1


def _soak_status() -> int:
    from autotrade.core.domain.redaction import redact_mapping
    from autotrade.persistence.models import SoakRun

    with _uow().session() as session:
        row = session.query(SoakRun).order_by(SoakRun.started_at.desc()).first()
        if row is None:
            print("soak=none")
            return 0
        print(
            redact_mapping(
                {
                    "soak_id": row.soak_id,
                    "account_id": row.account_id,
                    "started_at": str(row.started_at),
                    "ended_at": str(row.ended_at) if row.ended_at else None,
                    "owner_paused": bool(row.owner_paused),
                    "passed": bool(row.passed),
                    "unresolved_recon_at_end": row.unresolved_recon_at_end,
                }
            )
        )
    return 0


def _soak_abort(*, account_id: str, soak_id: str | None) -> int:
    from autotrade.core.certify.real_soak import abort_soak, get_active_soak

    uow = _uow()
    sid = soak_id
    if sid is None:
        active = get_active_soak(uow, account_id)
        if active is None:
            print("no active soak", file=sys.stderr)
            return 2
        sid = active.soak_id
    try:
        row = abort_soak(uow, sid)
    except KeyError:
        print(f"soak not found: {sid}", file=sys.stderr)
        return 2
    print(f"soak-aborted id={row.soak_id} owner_paused=True passed=False")
    return 0


def _cancel_intent(intent_id: str) -> int:
    """Cancel an ACKNOWLEDGED order intent.

    The adapter is chosen from the intent's own account mode (PAPER vs.
    DEMO) — same construction each mode already uses elsewhere in this file
    (`_switch_account` for PAPER, `_demo_test_connection` for DEMO/ccxt).

    Note (PAPER limitation, inherent to `PaperAdapter` — not something this
    command works around): `PaperAdapter` keeps its order book in-process
    memory only, never persisted. A PAPER cancel issued from a fresh
    headless invocation therefore only succeeds if it targets an order
    placed earlier in *this same process* (as the fault-injection tests
    do); against a genuinely separate process it will honestly resolve to
    CANCEL_UNKNOWN via the adapter's `NOT_FOUND` response, never a false
    "canceled". DEMO/ccxt orders live on the broker, so this limitation
    does not apply there.
    """
    from autotrade.core.oms.cancel import cancel_intent
    from autotrade.persistence.models import Account, OrderIntent

    uow = _uow()
    with uow.session() as session:
        intent = session.get(OrderIntent, intent_id)
        if intent is None:
            print(f"cancel-intent refused: unknown intent {intent_id}", file=sys.stderr)
            return 2
        account = session.get(Account, intent.account_id)
    mode = account.mode if account is not None else "PAPER"

    if mode == "DEMO":
        import os

        from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange

        if os.environ.get("AUTOTRADE_D1B_REAL") == "1":
            key, secret = _load_demo_creds(account.account_id if account else "demo-binance")
            adapter = CcxtDemoAdapter(
                api_key=key, api_secret=secret, endpoint="binance_spot_testnet"
            )
        else:
            adapter = CcxtDemoAdapter(exchange=FakeCcxtExchange(), endpoint="binance_spot_testnet")
    else:
        from autotrade.core.adapters.paper import PaperAdapter

        adapter = PaperAdapter()
    adapter.connect()

    result = cancel_intent(uow, adapter, intent_id=intent_id)
    if not result.ok:
        print(
            f"cancel-intent refused: intent={intent_id} state={result.state} "
            f"error={result.error}",
            file=sys.stderr,
        )
        return 2
    print(f"cancel-intent ok intent_id={intent_id} state={result.state}")
    return 0


async def _smoke_runtime() -> int:
    from autotrade.core.runtime import Runtime

    runtime = Runtime()

    async def echo(cmd: object) -> object:
        return {"echo": cmd}

    runtime.set_handler(echo)
    await runtime.start()
    try:
        result = await runtime.submit({"ping": True})
        print(result)
    finally:
        await runtime.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
