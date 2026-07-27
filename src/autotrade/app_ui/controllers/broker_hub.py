"""T030–T032 — Broker Hub controller: Paper/DEMO commands, Qt-free.

Contract (`contracts/ui-core-boundary.md`):
- `test_demo_connection` — no PIN. Builds the same `CcxtDemoAdapter` headless's
  `_demo_test_connection` does (real ccxt behind `AUTOTRADE_D1B_REAL=1`,
  `FakeCcxtExchange` otherwise) and returns a redacted capability summary.
  Connection errors are caught here — they must never raise into Qt code.
- `enable_demo` / `disable_demo` — cert-gated exactly like headless's
  `_enable_demo` / `_disable_demo`. A `CertificationNotValid` refusal is
  surfaced as a typed `EnableDemoResult`, never a raw exception into the view.
- `switch_account` — fail-closed, no PIN, mirrors headless's `_switch_account`.
  `SwitchRejected` reason codes (`not_flat`, `open_recon`,
  `unknown_or_submitting`) are surfaced verbatim in `SwitchAccountResult`.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from autotrade.app_ui.services.broker_hub import (
    TEST_CONNECTION_AUDIT_TYPE,
    BrokerHubState,
    build_broker_hub_state,
)
from autotrade.core.accounts.active import SwitchRejected, switch_active_account
from autotrade.core.accounts.bindings import bind_demo_strategy
from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.certify.records import CertificationNotValid, assert_cert_valid_for_trading
from autotrade.core.domain.redaction import redact_mapping, redact_text
from autotrade.core.oms.account_state import AccountStatus
from autotrade.persistence.models import Account, AuditEvent
from autotrade.persistence.uow import UnitOfWork

DEFAULT_DEMO_ACCOUNT_ID = "demo-binance"
DEFAULT_PAPER_ACCOUNT_ID = "paper1"
DEMO_ENDPOINT = "binance_spot_testnet"
KEYRING_SERVICE = "AutoTradeAI"

#: Factory for the ccxt exchange double/real client. Tests inject a fake
#: (e.g. `lambda: FakeCcxtExchange(disconnect=True)`); production leaves this
#: unset so `_build_adapter` follows headless's exact AUTOTRADE_D1B_REAL branch.
ExchangeFactory = Callable[[], Any]


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    """Outcome of `test_connection` — never raises into the view."""

    ok: bool
    capabilities: dict[str, Any] | None
    error_redacted: str | None


@dataclass(frozen=True, slots=True)
class EnableDemoResult:
    """Outcome of `enable_demo`. `refused_reason` is set, never an exception."""

    ok: bool
    account_id: str | None
    refused_reason: str | None


@dataclass(frozen=True, slots=True)
class SwitchAccountResult:
    """Outcome of `switch_account`. Fail-closed: `ok=False` always carries a reason."""

    ok: bool
    account_id: str | None
    mode: str | None
    #: `SwitchRejected` reason codes, e.g. ("not_flat",) or ("open_recon",).
    reasons: tuple[str, ...] = ()
    #: Non-SwitchRejected refusal, e.g. "no DEMO account configured".
    error: str | None = None


class BrokerHubController:
    """Bridges the Broker Hub screen to core accounts/certify/adapter commands."""

    def __init__(
        self,
        uow: UnitOfWork,
        *,
        exchange_factory: ExchangeFactory | None = None,
        demo_account_id: str = DEFAULT_DEMO_ACCOUNT_ID,
    ) -> None:
        self._uow = uow
        self._exchange_factory = exchange_factory
        self._demo_account_id = demo_account_id

    def snapshot(self) -> BrokerHubState:
        """Read-only projection for the Broker Hub page."""
        with self._uow.session() as session:
            return build_broker_hub_state(session)

    def test_connection(self, mode: str = "DEMO") -> ConnectionTestResult:
        """No PIN. Never raises into the view — errors come back redacted."""
        if mode != "DEMO":
            # Paper is a local adapter with no broker connection to probe.
            result = ConnectionTestResult(
                ok=True,
                capabilities={"adapter_id": "paper", "connected": True},
                error_redacted=None,
            )
        else:
            try:
                adapter = self._build_adapter()
                adapter.connect()
                caps = redact_mapping(adapter.get_capabilities())
                result = ConnectionTestResult(ok=True, capabilities=caps, error_redacted=None)
            except Exception as exc:  # noqa: BLE001 - contract: never raise into Qt
                result = ConnectionTestResult(
                    ok=False, capabilities=None, error_redacted=redact_text(str(exc))
                )
        self._record_test(mode=mode, result=result)
        return result

    def enable_demo(self, account_id: str | None = None) -> EnableDemoResult:
        """Cert-gated exactly like headless `_enable_demo`.

        Never lets `CertificationNotValid` (or a switch refusal) propagate as
        a raw exception — the view turns the typed result into a modal.
        """
        target = account_id or self._demo_account_id
        with self._uow.session() as session:
            try:
                assert_cert_valid_for_trading(session)
            except CertificationNotValid as exc:
                return EnableDemoResult(ok=False, account_id=None, refused_reason=str(exc))

            acc = session.get(Account, target)
            if acc is None:
                acc = Account(
                    account_id=target,
                    adapter_id="ccxt",
                    mode="DEMO",
                    endpoint=DEMO_ENDPOINT,
                    status=AccountStatus.READY.value,
                    eligibility="DEMO_CERTIFIED",
                    is_active=False,
                )
                session.add(acc)
                # Flush so `switch_active_account`'s `session.get` below (the
                # session has autoflush=False) sees this brand-new row rather
                # than raising SwitchRejected("unknown account: ..."). Mirrors
                # the fix already applied in test_cert_enable_gates.py's
                # `_try_enable` reference helper for this exact sequence.
                session.flush()
            else:
                acc.mode = "DEMO"
                acc.adapter_id = "ccxt"
                acc.status = AccountStatus.READY.value
                acc.eligibility = "DEMO_CERTIFIED"
            bind_demo_strategy(session, account_id=target)

            try:
                switch_active_account(session, target_account_id=target, position_qty=0.0)
            except SwitchRejected as exc:
                return EnableDemoResult(ok=False, account_id=target, refused_reason=str(exc))

            return EnableDemoResult(ok=True, account_id=target, refused_reason=None)

    def disable_demo(self) -> None:
        """Mirrors headless `_disable_demo` — no cert check needed to disable."""
        with self._uow.session() as session:
            for acc in session.query(Account).filter_by(mode="DEMO").all():
                acc.status = "SAFE_LOCK"
                acc.is_active = False
                session.add(acc)

    def switch_account(self, target: str, *, position_qty: float = 0.0) -> SwitchAccountResult:
        """Fail-closed, no PIN. `target` is `"paper"` or `"demo"`.

        Mirrors headless `_switch_account`: switching to "paper" provisions a
        default account if none exists; switching to "demo" requires one to
        already be provisioned (via `enable_demo`) and never auto-creates it.
        """
        with self._uow.session() as session:
            if target == "paper":
                acc = session.query(Account).filter_by(mode="PAPER").first()
                if acc is None:
                    acc = Account(
                        account_id=DEFAULT_PAPER_ACCOUNT_ID,
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
                    return SwitchAccountResult(
                        ok=False,
                        account_id=None,
                        mode=None,
                        error="no DEMO account configured — enable DEMO first",
                    )

            try:
                switch_active_account(
                    session, target_account_id=acc.account_id, position_qty=position_qty
                )
            except SwitchRejected as exc:
                reasons = tuple(str(exc).split(","))
                return SwitchAccountResult(
                    ok=False, account_id=acc.account_id, mode=acc.mode, reasons=reasons
                )

            return SwitchAccountResult(ok=True, account_id=acc.account_id, mode=acc.mode)

    def _build_adapter(self) -> CcxtDemoAdapter:
        """Same branch as headless `_demo_test_connection`: real behind the
        opt-in env var, `FakeCcxtExchange` otherwise. Tests bypass both via
        `exchange_factory`."""
        if self._exchange_factory is not None:
            return CcxtDemoAdapter(exchange=self._exchange_factory(), endpoint=DEMO_ENDPOINT)
        if os.environ.get("AUTOTRADE_D1B_REAL") == "1":
            from autotrade.persistence.secrets import SecretRef, load_secret

            key = load_secret(SecretRef(KEYRING_SERVICE, f"{self._demo_account_id}:api_key"))
            secret = load_secret(
                SecretRef(KEYRING_SERVICE, f"{self._demo_account_id}:api_secret")
            )
            if not key or not secret:
                raise RuntimeError("missing DEMO credentials in keyring")
            return CcxtDemoAdapter(api_key=key, api_secret=secret, endpoint=DEMO_ENDPOINT)
        return CcxtDemoAdapter(exchange=FakeCcxtExchange(), endpoint=DEMO_ENDPOINT)

    def _record_test(self, *, mode: str, result: ConnectionTestResult) -> None:
        with self._uow.session() as session:
            session.add(
                AuditEvent(
                    event_id=uuid4().hex,
                    type=TEST_CONNECTION_AUDIT_TYPE,
                    payload_redacted={
                        "mode": mode,
                        "ok": result.ok,
                        "capabilities": result.capabilities,
                        "error": result.error_redacted,
                    },
                    at=datetime.now(UTC),
                )
            )
