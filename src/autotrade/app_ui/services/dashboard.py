"""T013 — read-only Dashboard/Live-Monitor projections built from the UoW.

No Qt here: this is the read model the views render. It performs **no**
mutation and never touches the CCXT library — see
`specs/003-d1c-desktop-mvp/contracts/ui-core-boundary.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from autotrade.core.accounts.active import get_active_account
from autotrade.core.certify.records import get_cert
from autotrade.core.oms.fsm import IntentState
from autotrade.core.risk.kill_switch import KillSwitch
from autotrade.persistence.models import (
    BalanceSnapshot,
    MarketCandle,
    NotifyOutbox,
    Order,
    OrderIntent,
    ReconBreak,
)

#: Recon rows in any of these states still demand operator attention.
OPEN_RECON_STATUSES = ("OPEN", "UNRESOLVED", "open", "unresolved")

#: Outbox rows in any of these states are still owed to Telegram.
PENDING_OUTBOX_STATUSES = ("PENDING", "RETRY", "pending", "retry")

#: Intents whose broker-side outcome is not settled yet.
INFLIGHT_INTENT_STATES = (
    IntentState.UNKNOWN.value,
    IntentState.SUBMITTING.value,
    IntentState.CANCEL_UNKNOWN.value,
)

#: Modes the desktop may ever present as tradable. This is an ALLOWLIST on
#: purpose: LIVE is hard-disabled until the D1.1 gate (AGENTS.md), and a
#: blocklist would silently admit LIVE, a typo, or any mode added later.
TRADABLE_MODES = frozenset({"PAPER", "DEMO"})

#: Of those, the modes that additionally require a valid D1b certification.
CERT_REQUIRED_MODES = frozenset({"DEMO"})

#: Default page size for the Live Monitor. In-flight rows are NEVER counted
#: against it — see `build_live_monitor_page`.
DEFAULT_LIVE_MONITOR_LIMIT = 200

_TIMEFRAME_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class RecoveryStatus:
    """Coarse health rollup shown as the Dashboard badge."""

    OK = "OK"
    UNKNOWN_PENDING = "UNKNOWN_PENDING"
    RECON_OPEN = "RECON_OPEN"


@dataclass(frozen=True, slots=True)
class ActiveAccountView:
    """Mode/account/endpoint banner required on every trade-capable screen."""

    account_id: str | None
    mode: str | None
    endpoint_class: str | None
    cert_valid: bool
    is_ready: bool
    #: False for LIVE and for anything outside TRADABLE_MODES. Surfaced so the
    #: banner can shout instead of quietly rendering a forbidden mode.
    mode_allowed: bool = False

    @property
    def banner(self) -> str:
        if self.account_id is None:
            return "NO ACCOUNT — trading disabled"
        endpoint = self.endpoint_class or "local"
        text = f"{self.mode} · {self.account_id} · {endpoint}"
        if not self.mode_allowed:
            return f"{text} — MODE NOT PERMITTED"
        return text


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """Everything the Dashboard screen renders, in one immutable read."""

    account: ActiveAccountView
    equity: Decimal | None
    pnl_day: Decimal | None
    ks_level: int
    ks_latched: bool
    #: Raw `KillSwitch.triggers` payload (reason/level) when latched — the
    #: Kill-switch screen (T040) surfaces this verbatim; `None` when never
    #: triggered.
    ks_triggers: dict[str, Any] | None
    recovery_status: str
    open_recon_count: int
    outbox_backlog: int
    adapter_connected: bool
    data_age_sec: float | None

    @property
    def is_trading_blocked(self) -> bool:
        """True when the operator must act before any new exposure is sane.

        `account.is_ready` is part of the test: a DEMO account whose
        certification is missing or revoked, or any non-allowlisted mode, must
        read as blocked rather than merely "not ready".
        """
        return (
            not self.account.is_ready
            or self.ks_level > 0
            or self.recovery_status != RecoveryStatus.OK
            or not self.adapter_connected
        )


@dataclass(frozen=True, slots=True)
class LiveMonitorRow:
    """One row of the Live Monitor table — UNKNOWN intents are never hidden."""

    intent_id: str
    client_order_id: str
    state: str
    delivery_certainty: str | None
    symbol: str
    side: str
    qty: Decimal
    created_at: datetime

    @property
    def needs_attention(self) -> bool:
        return self.state in INFLIGHT_INTENT_STATES


@dataclass(frozen=True, slots=True)
class LiveMonitorPage:
    """A page of the Live Monitor that can never hide an in-flight intent.

    Paging is explicit rather than implicit: `truncated` tells the view how
    many settled rows were left out, so it can say "N more" instead of
    pretending the table is complete.
    """

    rows: list[LiveMonitorRow] = field(default_factory=list)
    total: int = 0
    inflight_total: int = 0
    truncated: int = 0

    @property
    def has_more(self) -> bool:
        return self.truncated > 0

    @property
    def attention_rows(self) -> list[LiveMonitorRow]:
        return [r for r in self.rows if r.needs_attention]


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; treat them as UTC."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _latest_balance(session: Session, account_id: str) -> BalanceSnapshot | None:
    return session.scalars(
        select(BalanceSnapshot)
        .where(BalanceSnapshot.account_id == account_id)
        .order_by(BalanceSnapshot.ts.desc(), BalanceSnapshot.id.desc())
        .limit(1)
    ).first()


def _first_balance_of_day(
    session: Session, account_id: str, day_start: datetime
) -> BalanceSnapshot | None:
    return session.scalars(
        select(BalanceSnapshot)
        .where(
            BalanceSnapshot.account_id == account_id,
            BalanceSnapshot.ts >= day_start,
        )
        .order_by(BalanceSnapshot.ts.asc(), BalanceSnapshot.id.asc())
        .limit(1)
    ).first()


def count_open_recon(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(ReconBreak)
            .where(ReconBreak.status.in_(OPEN_RECON_STATUSES))
        )
        or 0
    )


def count_outbox_backlog(session: Session) -> int:
    """Undelivered notifications, excluding dead-letters (those are terminal)."""
    return int(
        session.scalar(
            select(func.count())
            .select_from(NotifyOutbox)
            .where(
                NotifyOutbox.status.in_(PENDING_OUTBOX_STATUSES),
                NotifyOutbox.dead_letter.is_(False),
            )
        )
        or 0
    )


def count_inflight_intents(session: Session, account_id: str | None = None) -> int:
    stmt = (
        select(func.count())
        .select_from(OrderIntent)
        .where(OrderIntent.state.in_(INFLIGHT_INTENT_STATES))
    )
    if account_id is not None:
        stmt = stmt.where(OrderIntent.account_id == account_id)
    return int(session.scalar(stmt) or 0)


def build_active_account_view(session: Session) -> ActiveAccountView:
    account = get_active_account(session)
    if account is None:
        return ActiveAccountView(
            account_id=None,
            mode=None,
            endpoint_class=None,
            cert_valid=False,
            is_ready=False,
        )
    cert = get_cert(session)
    cert_valid = bool(cert is not None and cert.valid)
    # Allowlist, never a blocklist: `mode != "DEMO"` would have let LIVE (and
    # any future/typo'd mode) read as ready without a certificate.
    mode_allowed = account.mode in TRADABLE_MODES
    ready = (
        mode_allowed
        and account.status == "READY"
        and (account.mode not in CERT_REQUIRED_MODES or cert_valid)
    )
    return ActiveAccountView(
        account_id=account.account_id,
        mode=account.mode,
        endpoint_class=account.endpoint,
        cert_valid=cert_valid,
        is_ready=ready,
        mode_allowed=mode_allowed,
    )


def parse_timeframe_seconds(timeframe: str | None) -> int | None:
    """"15m" -> 900. Returns None for anything unparsable."""
    if not timeframe or len(timeframe) < 2:
        return None
    multiplier = _TIMEFRAME_UNIT_SECONDS.get(timeframe[-1].lower())
    if multiplier is None:
        return None
    try:
        value = int(timeframe[:-1])
    except ValueError:
        return None
    return value * multiplier if value > 0 else None


def _data_age_seconds(session: Session, now: datetime) -> float | None:
    """Age of the freshest *closed* candle — open candles are not data.

    Measured from the candle's CLOSE time (`open_time + timeframe`), not its
    open: a 15m candle that just closed is 0s old, not 900s. Using open_time
    reported every feed as one whole timeframe staler than it was.
    """
    candle = session.scalars(
        select(MarketCandle)
        .where(MarketCandle.is_closed.is_(True))
        .order_by(MarketCandle.open_time.desc())
        .limit(1)
    ).first()
    if candle is None:
        return None
    open_time = _as_utc(candle.open_time)
    if open_time is None:
        return None
    span = parse_timeframe_seconds(candle.timeframe) or 0
    close_time = open_time + timedelta(seconds=span)
    return max(0.0, (now - close_time).total_seconds())


def build_dashboard_snapshot(
    session: Session,
    *,
    now: datetime | None = None,
    adapter_connected: bool = False,
    ks_scope: str = "global",
) -> DashboardSnapshot:
    """Assemble the Dashboard read model.

    `adapter_connected` is runtime state owned by the process, not the DB, so
    the caller injects it. `now` is injectable to keep tests deterministic.
    """
    moment = now or datetime.now(UTC)
    account = build_active_account_view(session)
    ks = KillSwitch.load(session, ks_scope)

    equity: Decimal | None = None
    pnl_day: Decimal | None = None
    if account.account_id is not None:
        latest = _latest_balance(session, account.account_id)
        if latest is not None:
            equity = Decimal(str(latest.equity))
            day_start = moment.astimezone(UTC).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            opening = _first_balance_of_day(session, account.account_id, day_start)
            if opening is not None:
                pnl_day = equity - Decimal(str(opening.equity))

    open_recon = count_open_recon(session)
    inflight = count_inflight_intents(session, account.account_id)
    if open_recon > 0:
        recovery = RecoveryStatus.RECON_OPEN
    elif inflight > 0:
        recovery = RecoveryStatus.UNKNOWN_PENDING
    else:
        recovery = RecoveryStatus.OK

    return DashboardSnapshot(
        account=account,
        equity=equity,
        pnl_day=pnl_day,
        ks_level=ks.level,
        ks_latched=ks.latched,
        ks_triggers=ks.triggers,
        recovery_status=recovery,
        open_recon_count=open_recon,
        outbox_backlog=count_outbox_backlog(session),
        adapter_connected=adapter_connected,
        data_age_sec=_data_age_seconds(session, moment),
    )


def build_live_monitor_page(
    session: Session,
    *,
    account_id: str | None = None,
    limit: int = DEFAULT_LIVE_MONITOR_LIMIT,
) -> LiveMonitorPage:
    """Intents for the Live Monitor table.

    Hard guarantee: **every in-flight intent is returned**, whatever `limit`
    says. `limit` only caps the settled rows that pad the page out.

    The previous implementation applied `LIMIT` in SQL and only then sorted
    in-flight rows to the top — so with more intents than the limit, the
    UNKNOWN rows an operator most needs to see were the ones dropped.

    Both settled and in-flight rows are ordered most-recent-first by
    `created_at` (migration `0003_d1c_ks_intent_ts`), with `intent_id` as a
    stable tiebreaker for rows sharing a timestamp.
    """
    if limit < 0:
        raise ValueError("limit must be >= 0")

    def scoped(stmt: Select) -> Select:
        if account_id is None:
            return stmt
        return stmt.where(OrderIntent.account_id == account_id)

    inflight = list(
        session.scalars(
            scoped(select(OrderIntent).where(OrderIntent.state.in_(INFLIGHT_INTENT_STATES)))
            .order_by(OrderIntent.created_at.desc(), OrderIntent.intent_id)
        ).all()
    )

    settled: list[OrderIntent] = []
    settled_slots = max(0, limit - len(inflight))
    if settled_slots:
        settled = list(
            session.scalars(
                scoped(
                    select(OrderIntent).where(
                        OrderIntent.state.not_in(INFLIGHT_INTENT_STATES)
                    )
                )
                .order_by(OrderIntent.created_at.desc(), OrderIntent.intent_id)
                .limit(settled_slots)
            ).all()
        )

    total = int(
        session.scalar(scoped(select(func.count()).select_from(OrderIntent))) or 0
    )

    intents = inflight + settled
    certainty: dict[str, str] = {}
    if intents:
        orders = session.scalars(
            select(Order).where(Order.intent_id.in_([i.intent_id for i in intents]))
        ).all()
        for order in orders:
            certainty[order.intent_id] = order.delivery_certainty

    rows = [
        LiveMonitorRow(
            intent_id=i.intent_id,
            client_order_id=i.client_order_id,
            state=i.state,
            delivery_certainty=certainty.get(i.intent_id),
            symbol=i.symbol,
            side=i.side,
            qty=Decimal(str(i.qty)),
            created_at=_as_utc(i.created_at),
        )
        for i in intents
    ]
    return LiveMonitorPage(
        rows=rows,
        total=total,
        inflight_total=len(inflight),
        truncated=max(0, total - len(rows)),
    )
