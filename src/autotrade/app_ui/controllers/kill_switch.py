"""T042 — Kill-switch page: manual Flatten controller (No PIN, confirm dialog only).

Contract (`contracts/ui-core-boundary.md`): `flatten_local` is **No PIN**,
"Confirm dialog only" — unlike Pause (T040), which has no dialog at all,
the view is required to ask "Continue?" before this controller ever runs,
because unlike Pause this submits a real closing order to the active
account's adapter.

Owner decision 2 (T042, see `autotrade.core.oms.flatten` and
`RiskEngine.check_increase`): a flatten must go through even while the
kill-switch is elevated (L1+). This controller reads the *real*, persisted
kill-switch level — the same `KillSwitch.load(session, scope)` /
`DEFAULT_KS_SCOPE` the Tray/KS page itself reads — and reflects it into the
ephemeral `AccountGate` it builds for the submitter, so the `reduce_only`
bypass is actually exercised end-to-end by the real button, not only
proven in isolated `RiskEngine` unit tests.

Placement: a new, small, focused controller rather than an extension of
`TrayController` (today has no notion of adapters/risk/gate at all — its
scope is read-only snapshots + the no-PIN Pause path) or
`BrokerHubController` (Broker Hub connectivity/account-lifecycle concerns,
not order submission). Adapter construction mirrors
`BrokerHubController._build_adapter()`: real ccxt behind
`AUTOTRADE_D1B_REAL=1`, `FakeCcxtExchange` otherwise; tests inject
`exchange_factory` to bypass both branches, same precedent.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from autotrade.app_ui.controllers.tray import DEFAULT_KS_SCOPE
from autotrade.core.accounts.active import get_active_account
from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter, FakeCcxtExchange
from autotrade.core.adapters.protocol import BrokerAdapter
from autotrade.core.adapters.registry import create_adapter
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.core.domain.money import d
from autotrade.core.domain.redaction import redact_text
from autotrade.core.oms.account_state import AccountGate, AccountStatus
from autotrade.core.oms.flatten import flatten_position
from autotrade.core.oms.submit import DurableSubmitter
from autotrade.core.risk.engine import RiskEngine, RiskLimits
from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.persistence.models import AuditEvent
from autotrade.persistence.uow import UnitOfWork

FLATTEN_AUDIT_TYPE = "ui.kill_switch.flatten"
KEYRING_SERVICE = "AutoTradeAI"

#: Same fallback used by `real_lifecycles.run_round_trip_lifecycles`: a real
#: market-price fetch for `CcxtDemoAdapter` does not exist today (no
#: `fetch_ticker`/`get_ticker` on the adapter) — known limitation, flagged
#: in the T042 report, not solved here.
DEFAULT_FLATTEN_PRICE = d("50000")

#: Testnet-friendly limits mirroring `real_lifecycles.run_round_trip_lifecycles`
#: — Binance Spot Testnet dust/evidence sizes can exceed the app's tight
#: default `RiskLimits()`.
_FLATTEN_RISK_LIMITS = RiskLimits(max_notional=d("100000"), max_qty=d("10"))

#: Factory for the ccxt exchange double/real client — same precedent as
#: `BrokerHubController.ExchangeFactory`. Tests inject a fake; production
#: leaves this unset so `_build_adapter` follows the exact AUTOTRADE_D1B_REAL
#: branch.
ExchangeFactory = Callable[[], Any]


@dataclass(frozen=True, slots=True)
class FlattenUiResult:
    """Outcome of a manual Flatten. The view turns this into a modal and
    NEVER lets a raw exception from this controller reach Qt."""

    ok: bool
    no_active_account: bool = False
    qty_closed: Decimal | None = None
    message: str = ""


class KillSwitchController:
    """Builds the flatten submission stack for the active account and calls
    `autotrade.core.oms.flatten.flatten_position`."""

    def __init__(
        self,
        uow: UnitOfWork,
        *,
        ks_scope: str = DEFAULT_KS_SCOPE,
        exchange_factory: ExchangeFactory | None = None,
    ) -> None:
        self._uow = uow
        self._ks_scope = ks_scope
        self._exchange_factory = exchange_factory

    def flatten(self) -> FlattenUiResult:
        """No PIN — the view's confirm dialog is the only gate before this
        runs. Never raises into Qt: every failure mode comes back typed."""
        with self._uow.session() as session:
            account = get_active_account(session)
            if account is None or not account.adapter_id:
                return FlattenUiResult(
                    ok=False,
                    no_active_account=True,
                    message="No active account configured — nothing to flatten.",
                )
            account_id = account.account_id
            adapter_id = account.adapter_id
            ks_level = KillSwitch.load(session, self._ks_scope).level

        try:
            adapter = self._build_adapter(adapter_id, account_id=account_id)
            if not adapter.connected:
                adapter.connect()
        except Exception as exc:  # noqa: BLE001 - contract: never raise into Qt
            result = FlattenUiResult(
                ok=False, message=f"Could not reach adapter: {redact_text(str(exc))}"
            )
            self._audit(account_id=account_id, result=result)
            return result

        symbol = D1B_ALLOWLIST.symbol
        price = DEFAULT_FLATTEN_PRICE
        if hasattr(adapter, "exchange") and hasattr(adapter.exchange, "last_price"):
            price = d(str(adapter.exchange.last_price))

        # Reflect the *real* persisted kill-switch level into the ephemeral
        # gate so the reduce_only bypass (Decision 2) is genuinely exercised
        # for this button, not trivially always-READY.
        gate = AccountGate(
            account_id=account_id,
            status=AccountStatus.READY if ks_level < 1 else AccountStatus.SAFE_LOCK,
        )
        risk = RiskEngine(limits=_FLATTEN_RISK_LIMITS)
        submitter = DurableSubmitter(uow=self._uow, adapter=adapter, risk=risk, gate=gate)

        try:
            core_result = flatten_position(
                submitter, account_id=account_id, symbol=symbol, price=price
            )
        except Exception as exc:  # noqa: BLE001 - contract: never raise into Qt
            result = FlattenUiResult(ok=False, message=f"Flatten failed: {redact_text(str(exc))}")
            self._audit(account_id=account_id, result=result)
            return result

        if not core_result.ok:
            result = FlattenUiResult(ok=False, message=f"Flatten failed: {core_result.error}")
        elif core_result.qty_closed is not None and core_result.qty_closed > 0:
            result = FlattenUiResult(
                ok=True,
                qty_closed=core_result.qty_closed,
                message=f"Flattened {core_result.qty_closed} {symbol}.",
            )
        else:
            result = FlattenUiResult(
                ok=True, qty_closed=d("0"), message="Already flat — nothing to close."
            )
        self._audit(account_id=account_id, result=result)
        return result

    def _build_adapter(self, adapter_id: str, *, account_id: str) -> BrokerAdapter:
        if adapter_id == "paper":
            # NOTE (limitation): PaperAdapter keeps position state only in
            # its own in-memory dict, not persisted — a freshly constructed
            # PaperAdapter starts flat regardless of the `positions` ledger
            # table. Flatten against a PAPER account will therefore usually
            # report "already flat" rather than reflecting the persisted
            # position. Out of scope for T042; flagged in the report.
            return create_adapter("paper")
        if adapter_id != "ccxt":
            raise RuntimeError(f"unsupported adapter_id: {adapter_id}")
        if self._exchange_factory is not None:
            return CcxtDemoAdapter(
                exchange=self._exchange_factory(), endpoint=D1B_ALLOWLIST.endpoint_class
            )
        if os.environ.get("AUTOTRADE_D1B_REAL") == "1":
            from autotrade.persistence.secrets import SecretRef, load_secret

            key = load_secret(SecretRef(KEYRING_SERVICE, f"{account_id}:api_key"))
            secret = load_secret(SecretRef(KEYRING_SERVICE, f"{account_id}:api_secret"))
            if not key or not secret:
                raise RuntimeError("missing DEMO credentials in keyring")
            return CcxtDemoAdapter(
                api_key=key, api_secret=secret, endpoint=D1B_ALLOWLIST.endpoint_class
            )
        return CcxtDemoAdapter(exchange=FakeCcxtExchange(), endpoint=D1B_ALLOWLIST.endpoint_class)

    def _audit(self, *, account_id: str, result: FlattenUiResult) -> None:
        with self._uow.session() as session:
            session.add(
                AuditEvent(
                    event_id=uuid4().hex,
                    type=FLATTEN_AUDIT_TYPE,
                    payload_redacted={
                        "account_id": account_id,
                        "ok": result.ok,
                        "qty_closed": (
                            None if result.qty_closed is None else str(result.qty_closed)
                        ),
                        "message": redact_text(result.message),
                    },
                    at=datetime.now(UTC),
                )
            )
