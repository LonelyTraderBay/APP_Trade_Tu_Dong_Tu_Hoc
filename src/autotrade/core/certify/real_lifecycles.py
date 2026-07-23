"""Real-testnet (or injected) DEMO round-trip lifecycle runner (SC-004)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal

from autotrade.core.adapters.ccxt_demo.adapter import CcxtDemoAdapter
from autotrade.core.adapters.protocol import BrokerAdapter
from autotrade.core.certify.lifecycle import count_real_lifecycles, record_completed_lifecycle
from autotrade.core.domain.allowlist import D1B_ALLOWLIST, AllowlistViolation
from autotrade.core.domain.money import d
from autotrade.core.oms.account_state import AccountGate, AccountStatus
from autotrade.core.oms.submit import DurableSubmitter, SubmitRequest
from autotrade.core.risk.engine import RiskEngine, RiskLimits
from autotrade.persistence.uow import UnitOfWork

REAL_ENV = "AUTOTRADE_D1B_REAL"


@dataclass
class LifecycleRunResult:
    requested: int
    completed: int
    total_real_count: int
    errors: list[str]


def require_real_env() -> None:
    if os.environ.get(REAL_ENV) != "1":
        raise RuntimeError(f"{REAL_ENV}=1 required for real DEMO lifecycle / soak runners")


def _position_qty(adapter: BrokerAdapter, symbol: str) -> Decimal:
    for p in adapter.get_positions():
        if p.get("symbol") == symbol:
            return d(str(p.get("qty") or "0"))
    return d("0")


def _flat(adapter: BrokerAdapter, symbol: str) -> bool:
    return abs(_position_qty(adapter, symbol)) < d("1e-12")


def run_round_trip_lifecycles(
    *,
    uow: UnitOfWork,
    adapter: BrokerAdapter,
    account_id: str,
    count: int = 50,
    qty: Decimal | None = None,
    price: Decimal | None = None,
    source: str = "real_testnet",
) -> LifecycleRunResult:
    """Execute N entry→exit round-trips; record only when flat and source allowed.

    For production evidence use source='real_testnet' and a live CcxtDemoAdapter.
    Tests may inject FakeCcxtExchange-backed adapter; only real_testnet increments cert.
    """
    if count < 1:
        raise ValueError("count must be >= 1")
    if not adapter.connected:
        adapter.connect()

    symbol = D1B_ALLOWLIST.symbol
    trade_qty = qty or d("0.001")
    # Prefer adapter last price when fake; else use provided / default
    trade_price = price
    if trade_price is None:
        trade_price = d("50000")
        if hasattr(adapter, "exchange") and hasattr(adapter.exchange, "last_price"):
            trade_price = d(str(adapter.exchange.last_price))

    gate = AccountGate(account_id=account_id, status=AccountStatus.READY)
    # Evidence sizes are tiny; widen risk for testnet dust qty if needed
    risk = RiskEngine(limits=RiskLimits(max_notional=d("100000"), max_qty=d("10")))
    submitter = DurableSubmitter(uow=uow, adapter=adapter, risk=risk, gate=gate)

    completed = 0
    errors: list[str] = []

    for i in range(count):
        if not _flat(adapter, symbol):
            # Attempt flatten before counting a new cycle
            flat_err = _flatten(submitter, account_id=account_id, symbol=symbol, price=trade_price)
            if flat_err or not _flat(adapter, symbol):
                errors.append(f"cycle_{i}:not_flat_start:{flat_err}")
                break

        buy = submitter.submit(
            SubmitRequest(
                account_id=account_id,
                symbol=symbol,
                side="buy",
                qty=trade_qty,
                price=trade_price,
            )
        )
        if not buy.ok:
            errors.append(f"cycle_{i}:entry_fail:{buy.error}")
            break
        entry_id = buy.intent_id

        sell = submitter.submit(
            SubmitRequest(
                account_id=account_id,
                symbol=symbol,
                side="sell",
                qty=trade_qty,
                price=trade_price,
            )
        )
        if not sell.ok:
            errors.append(f"cycle_{i}:exit_fail:{sell.error}")
            break
        exit_id = sell.intent_id

        if not _flat(adapter, symbol):
            errors.append(f"cycle_{i}:not_flat_after_exit")
            break

        with uow.session() as session:
            # Reject if UNKNOWN intents linger
            from sqlalchemy import select

            from autotrade.core.oms.fsm import IntentState
            from autotrade.persistence.models import OrderIntent

            unknown = session.scalars(
                select(OrderIntent).where(
                    OrderIntent.account_id == account_id,
                    OrderIntent.state == IntentState.UNKNOWN.value,
                )
            ).first()
            if unknown is not None:
                errors.append(f"cycle_{i}:unknown_intent")
                break
            recorded = record_completed_lifecycle(
                session,
                account_id=account_id,
                source=source,
                entry_intent_id=entry_id,
                exit_intent_id=exit_id,
                notes=f"cycle={i + 1}",
            )
            if source == "real_testnet" and recorded is None:
                errors.append(f"cycle_{i}:record_rejected")
                break

        completed += 1

    with uow.session() as session:
        total = count_real_lifecycles(session, account_id=account_id)

    return LifecycleRunResult(
        requested=count,
        completed=completed,
        total_real_count=total,
        errors=errors,
    )


def _flatten(
    submitter: DurableSubmitter,
    *,
    account_id: str,
    symbol: str,
    price: Decimal,
) -> str | None:
    qty = _position_qty(submitter.adapter, symbol)
    if abs(qty) < d("1e-12"):
        return None
    side = "sell" if qty > 0 else "buy"
    result = submitter.submit(
        SubmitRequest(
            account_id=account_id,
            symbol=symbol,
            side=side,
            qty=abs(qty),
            price=price,
        )
    )
    if not result.ok:
        return result.error or "flatten_failed"
    return None


def build_real_adapter(*, account_id: str = "demo-binance") -> CcxtDemoAdapter:
    """Construct CcxtDemoAdapter from keyring; requires AUTOTRADE_D1B_REAL=1."""
    require_real_env()
    from autotrade.persistence.secrets import SecretRef, load_secret

    service = "AutoTradeAI"
    key = load_secret(SecretRef(service, f"{account_id}:api_key"))
    secret = load_secret(SecretRef(service, f"{account_id}:api_secret"))
    if not key or not secret:
        raise AllowlistViolation("DEMO credentials missing in keyring")
    adapter = CcxtDemoAdapter(
        api_key=key,
        api_secret=secret,
        endpoint="binance_spot_testnet",
    )
    return adapter


def lifecycle_count_from_env(default: int = 50) -> int:
    raw = os.environ.get("AUTOTRADE_D1B_LIFECYCLE_COUNT")
    if raw is None or raw == "":
        return default
    return max(1, int(raw))
