"""Post-audit fix — desktop Startup Recovery orchestration (FR-004), Qt-free.

`run_startup_recovery` (`core/oms/recovery.py`) is a fully implemented,
D1a-tested gate — it restores the kill-switch (never auto-lowers), checks
adapter connectivity, order-list pagination completeness, data freshness and
unresolved recon breaks, then either locks the `AccountGate` with reasons or
marks it READY. Before this module it was invoked only from tests and from
D1b's soak/lifecycle harnesses (`core/certify/real_soak.py`,
`scripts/finalize_orphan_soak.py`) — never from the desktop entrypoint. That
let the Owner open MainWindow and reach trading screens (Broker Hub,
Kill-switch, Live Monitor) after a crash, sleep/resume, or any interrupted
session without the checklist ever running.

`entrypoints/desktop.py::main()` calls `run_desktop_startup_recovery`
synchronously — after the single-instance guard, before `_run_gui()` shows
the window and before the `--check` banner is printed — so both reflect
POST-recovery state.

Adapter construction mirrors `BrokerHubController._build_adapter()` /
`KillSwitchController._build_adapter()` (real ccxt behind
`AUTOTRADE_D1B_REAL=1`, `FakeCcxtExchange` otherwise): same precedent, a
third near-identical private helper rather than a shared one, kept local to
this module since it is Qt-free and must stay importable without PySide6.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from autotrade.app_ui.services.clock_checkpoint import (
    read_last_wall_checkpoint,
    write_wall_checkpoint,
)
from autotrade.app_ui.services.dashboard import count_open_recon, parse_timeframe_seconds
from autotrade.core.accounts.active import get_active_account
from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.adapters.registry import create_adapter
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.core.domain.clock import ClockPort, detect_clock_jump
from autotrade.core.oms.account_state import AccountGate
from autotrade.core.oms.recovery import RecoveryResult, run_startup_recovery
from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.persistence.models import MarketCandle
from autotrade.persistence.uow import UnitOfWork

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from autotrade.core.adapters.protocol import BrokerAdapter

KEYRING_SERVICE = "AutoTradeAI"

#: Factory for the ccxt exchange double/real client — same precedent as
#: `BrokerHubController.ExchangeFactory` / `KillSwitchController.ExchangeFactory`.
#: Tests inject a fake; production leaves this unset so `_build_adapter`
#: follows the exact `AUTOTRADE_D1B_REAL` branch.
ExchangeFactory = Callable[[], Any]

#: Same scope `TrayController`/`BrokerHubController`/`KillSwitchController`
#: use by default (`app_ui/controllers/tray.py::DEFAULT_KS_SCOPE`) — kept as
#: a local literal rather than imported so `services/` does not reach into
#: `controllers/` (no existing precedent for that direction in this tree).
DEFAULT_KS_SCOPE = "global"

#: A closed candle older than this many multiples of its own timeframe reads
#: as stale for Startup Recovery — the same signal the Dashboard badge shows
#: as a value (`dashboard._data_age_seconds`), turned into a pass/fail gate
#: here. No candle rows at all (e.g. a PAPER-only install that never ingested
#: market data) is treated as fresh: recovery has no evidence of staleness to
#: fail closed on, so the adapter-connect and recon checks carry the
#: fail-closed weight instead.
STALE_TIMEFRAME_MULTIPLE = 3


def _is_data_fresh(session: Session, *, now: datetime) -> bool:
    candle = session.scalars(
        select(MarketCandle)
        .where(MarketCandle.is_closed.is_(True))
        .order_by(MarketCandle.open_time.desc())
        .limit(1)
    ).first()
    if candle is None:
        return True
    open_time = candle.open_time
    if open_time.tzinfo is None:  # SQLite hands back naive datetimes.
        open_time = open_time.replace(tzinfo=UTC)
    span = parse_timeframe_seconds(candle.timeframe) or 0
    close_time = open_time + timedelta(seconds=span)
    age = max(0.0, (now - close_time).total_seconds())
    threshold = max(span, 60) * STALE_TIMEFRAME_MULTIPLE
    return age <= threshold


def _build_adapter(
    adapter_id: str,
    *,
    account_id: str,
    endpoint: str | None,
    exchange_factory: ExchangeFactory | None,
) -> BrokerAdapter:
    """Same branch `BrokerHubController`/`KillSwitchController` already use:
    real ccxt behind `AUTOTRADE_D1B_REAL=1`, `FakeCcxtExchange` otherwise."""
    if adapter_id == "paper":
        return create_adapter("paper")
    if adapter_id != "ccxt":
        raise RuntimeError(f"unsupported adapter_id: {adapter_id}")
    endpoint_class = endpoint or D1B_ALLOWLIST.endpoint_class
    if exchange_factory is not None:
        return CcxtDemoAdapter(exchange=exchange_factory(), endpoint=endpoint_class)
    if os.environ.get("AUTOTRADE_D1B_REAL") == "1":
        from autotrade.persistence.secrets import SecretRef, load_secret

        key = load_secret(SecretRef(KEYRING_SERVICE, f"{account_id}:api_key"))
        secret = load_secret(SecretRef(KEYRING_SERVICE, f"{account_id}:api_secret"))
        if not key or not secret:
            raise RuntimeError("missing DEMO credentials in keyring")
        return CcxtDemoAdapter(api_key=key, api_secret=secret, endpoint=endpoint_class)
    return CcxtDemoAdapter(exchange=FakeCcxtExchange(), endpoint=endpoint_class)


def run_desktop_startup_recovery(
    uow: UnitOfWork,
    *,
    ks_scope: str = DEFAULT_KS_SCOPE,
    exchange_factory: ExchangeFactory | None = None,
) -> RecoveryResult | None:
    """Run the Startup Recovery gate for the desktop's active account.

    Returns `None` when there is no active account yet — a fresh install
    with nothing provisioned has nothing to recover; that is not a failure.

    Never raises. An unreadable/unmigrated DB also reads as "nothing to
    recover" (the `--check` banner and `MainWindow.refresh_banner()` already
    degrade gracefully for that case — see
    `tests/unit/test_desktop_entrypoint.py::test_check_mode_survives_an_unmigrated_database`).
    An adapter that cannot even be constructed (e.g. missing DEMO keyring
    secrets) folds into a locked `RecoveryResult` instead of crashing,
    matching `BrokerHubController`/`KillSwitchController`'s contract that a
    connect failure never becomes an unhandled exception.

    ADR-D12 (clock-skew detection): also compares the current wall clock
    against the checkpoint the last successful launch wrote
    (`app_ui/services/clock_checkpoint.py`, `AppSetting`-backed). Only the
    cross-restart-safe half of `detect_clock_jump` applies at launch — a
    backward wall-clock move since that checkpoint — because
    `time.monotonic()` has no meaning across process restarts (see that
    function's docstring); `last_mono` is deliberately `None` here. A
    detected jump locks the gate through the same `gate.lock(...)` path
    `run_startup_recovery` already uses for its own reasons, even overriding
    an otherwise-READY result — this app must never silently trade through a
    suspicious clock state. The checkpoint is advanced only after a fully
    successful (non-locked) recovery, so a locked/failed launch never
    overwrites the last known-good checkpoint with a bad one. True
    intra-session sleep/resume detection (the monotonic-divergence half of
    `detect_clock_jump`) needs a same-process `last_mono` baseline, which
    requires a periodic recheck while the app is running — no such loop
    exists yet; see ADR-D12's task note for the follow-up.
    """
    try:
        with uow.session() as session:
            account = get_active_account(session)
            if account is None or not account.adapter_id:
                return None
            account_id = account.account_id
            adapter_id = account.adapter_id
            endpoint = account.endpoint
    except Exception:  # noqa: BLE001 - unmigrated/unavailable DB: nothing to recover
        return None

    gate = AccountGate(account_id=account_id)

    try:
        adapter = _build_adapter(
            adapter_id,
            account_id=account_id,
            endpoint=endpoint,
            exchange_factory=exchange_factory,
        )
    except Exception as exc:  # noqa: BLE001 - contract: never raise, fold into lock
        gate.begin_recovery()
        gate.lock(f"connect_fail:{exc}")
        return RecoveryResult(ready=False, status=gate.status, reasons=list(gate.reasons))

    try:
        clock = ClockPort()
        with uow.session() as session:
            ks = KillSwitch.load(session, ks_scope)
            unresolved_breaks = count_open_recon(session) > 0
            data_fresh = _is_data_fresh(session, now=datetime.now(UTC))
            last_wall_checkpoint = read_last_wall_checkpoint(session)

        result = run_startup_recovery(
            uow=uow,
            adapter=adapter,
            gate=gate,
            ks=ks,
            auth_ok=True,
            pagination_complete=True,
            data_fresh=data_fresh,
            unresolved_breaks=unresolved_breaks,
        )

        clock_check = detect_clock_jump(
            clock, last_wall=last_wall_checkpoint, last_mono=None
        )
        if clock_check.jumped:
            gate.lock(clock_check.reason or "clock_skew_detected")
            result = RecoveryResult(
                ready=False, status=gate.status, reasons=list(gate.reasons)
            )

        if result.ready:
            with uow.session() as session:
                write_wall_checkpoint(session, clock.now_utc())

        return result
    except Exception as exc:  # noqa: BLE001 - contract: never raise, fold into lock
        gate.lock(f"recovery_error:{exc}")
        return RecoveryResult(ready=False, status=gate.status, reasons=list(gate.reasons))
