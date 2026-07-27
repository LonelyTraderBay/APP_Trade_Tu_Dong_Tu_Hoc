"""T013 — Dashboard / Live Monitor read models (no Qt required)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from autotrade.app_ui.services.dashboard import (
    DEFAULT_LIVE_MONITOR_LIMIT,
    RecoveryStatus,
    build_active_account_view,
    build_dashboard_snapshot,
    build_live_monitor_page,
    parse_timeframe_seconds,
)
from autotrade.core.domain.money import d
from autotrade.core.oms.fsm import DeliveryCertainty, IntentState
from autotrade.persistence.models import (
    Account,
    BalanceSnapshot,
    CertificationRecord,
    KillSwitchState,
    MarketCandle,
    NotifyOutbox,
    Order,
    OrderIntent,
    ReconBreak,
)
from autotrade.persistence.uow import UnitOfWork

NOW = datetime(2026, 7, 27, 12, 30, tzinfo=UTC)
DAY = NOW.replace(hour=0, minute=0, second=0, microsecond=0)


def _seed_account(session, *, mode: str = "PAPER", status: str = "READY") -> None:
    session.add(
        Account(
            account_id="paper1",
            adapter_id="paper",
            mode=mode,
            endpoint="local",
            status=status,
            eligibility="ELIGIBLE",
            is_active=True,
        )
    )


def _seed_balances(session) -> None:
    session.add(
        BalanceSnapshot(
            account_id="paper1",
            equity=d("1000"),
            ts=DAY + timedelta(minutes=5),
            source="paper",
        )
    )
    session.add(
        BalanceSnapshot(
            account_id="paper1",
            equity=d("1150"),
            ts=NOW - timedelta(minutes=30),
            source="paper",
        )
    )


@pytest.mark.d1c
def test_snapshot_happy_path(migrated_uow: UnitOfWork) -> None:
    with migrated_uow.session() as session:
        _seed_account(session)
        _seed_balances(session)
        # Opened 30m ago on a 15m timeframe → closed 15m ago → 900s old.
        session.add(
            MarketCandle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time=NOW - timedelta(seconds=1800),
                open=d("1"),
                high=d("1"),
                low=d("1"),
                close=d("1"),
                volume=d("1"),
                is_closed=True,
            )
        )

    with migrated_uow.session() as session:
        snap = build_dashboard_snapshot(session, now=NOW, adapter_connected=True)

    assert snap.account.account_id == "paper1"
    assert snap.account.mode == "PAPER"
    assert snap.account.is_ready is True  # PAPER never needs a certificate
    assert snap.account.mode_allowed is True
    assert snap.equity == Decimal("1150")
    assert snap.pnl_day == Decimal("150")
    assert snap.ks_level == 0
    assert snap.recovery_status == RecoveryStatus.OK
    assert snap.outbox_backlog == 0
    assert snap.data_age_sec == pytest.approx(900.0)
    assert snap.is_trading_blocked is False
    assert "PAPER" in snap.account.banner


@pytest.mark.d1c
def test_snapshot_without_account_is_empty_not_crashing(migrated_uow: UnitOfWork) -> None:
    with migrated_uow.session() as session:
        snap = build_dashboard_snapshot(session, now=NOW)

    assert snap.account.account_id is None
    assert snap.equity is None
    assert snap.pnl_day is None
    assert snap.data_age_sec is None
    assert snap.is_trading_blocked is True
    assert "NO ACCOUNT" in snap.account.banner


@pytest.mark.d1c
def test_demo_account_is_not_ready_without_valid_cert(migrated_uow: UnitOfWork) -> None:
    with migrated_uow.session() as session:
        _seed_account(session, mode="DEMO")
        session.add(
            CertificationRecord(
                cert_id="cert-x",
                tuple_key="binance|spot|binance_spot_testnet|BTC/USDT|15m",
                valid=False,
            )
        )

    with migrated_uow.session() as session:
        snap = build_dashboard_snapshot(session, now=NOW)

    assert snap.account.mode == "DEMO"
    assert snap.account.cert_valid is False
    assert snap.account.is_ready is False
    assert snap.account.mode_allowed is True  # DEMO is allowed, just not certified
    # Regression: a DEMO account without a valid cert must read as BLOCKED,
    # not merely "not ready".
    assert snap.is_trading_blocked is True


@pytest.mark.d1c
def test_open_recon_outranks_unknown_in_recovery_status(migrated_uow: UnitOfWork) -> None:
    with migrated_uow.session() as session:
        _seed_account(session)
        session.add(
            ReconBreak(type="position", payload={}, status="OPEN", at=NOW)
        )
        session.add(
            OrderIntent(
                intent_id="i1",
                client_order_id="c1",
                state=IntentState.UNKNOWN.value,
                account_id="paper1",
                side="buy",
                qty=d("1"),
                symbol="BTC/USDT",
            )
        )

    with migrated_uow.session() as session:
        snap = build_dashboard_snapshot(session, now=NOW, adapter_connected=True)

    assert snap.recovery_status == RecoveryStatus.RECON_OPEN
    assert snap.open_recon_count == 1
    assert snap.is_trading_blocked is True


@pytest.mark.d1c
def test_kill_switch_level_and_outbox_backlog(migrated_uow: UnitOfWork) -> None:
    with migrated_uow.session() as session:
        _seed_account(session)
        session.add(
            KillSwitchState(scope="global", level=2, triggers_json=None, latched=True)
        )
        session.add(NotifyOutbox(event_id="e1", status="PENDING", dead_letter=False))
        session.add(NotifyOutbox(event_id="e2", status="RETRY", dead_letter=False))
        # Dead letters are terminal: they are not backlog anymore.
        session.add(NotifyOutbox(event_id="e3", status="PENDING", dead_letter=True))
        session.add(NotifyOutbox(event_id="e4", status="SENT", dead_letter=False))

    with migrated_uow.session() as session:
        snap = build_dashboard_snapshot(session, now=NOW, adapter_connected=True)

    assert snap.ks_level == 2
    assert snap.ks_latched is True
    assert snap.outbox_backlog == 2
    assert snap.is_trading_blocked is True


@pytest.mark.d1c
def test_open_candle_does_not_count_as_fresh_data(migrated_uow: UnitOfWork) -> None:
    with migrated_uow.session() as session:
        _seed_account(session)
        session.add(
            MarketCandle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time=NOW,
                open=d("1"),
                high=d("1"),
                low=d("1"),
                close=d("1"),
                volume=d("1"),
                is_closed=False,
            )
        )

    with migrated_uow.session() as session:
        snap = build_dashboard_snapshot(session, now=NOW)

    assert snap.data_age_sec is None


@pytest.mark.parametrize(
    ("mode", "status", "expect_ready", "expect_allowed"),
    [
        ("PAPER", "READY", True, True),
        ("PAPER", "NEW", False, True),
        ("LIVE", "READY", False, False),
        ("live", "READY", False, False),  # case matters — allowlist is exact
        ("FUTURES", "READY", False, False),
        ("", "READY", False, False),
    ],
)
@pytest.mark.d1c
def test_only_allowlisted_modes_can_read_as_ready(
    migrated_uow: UnitOfWork,
    mode: str,
    status: str,
    expect_ready: bool,
    expect_allowed: bool,
) -> None:
    """Regression: `mode != "DEMO"` was a blocklist and let LIVE read as ready.

    AGENTS.md hard-disables LIVE until the D1.1 gate; the read model must
    fail closed on its own rather than trusting the core switch guard.
    """
    with migrated_uow.session() as session:
        session.add(
            Account(
                account_id="acc1",
                adapter_id="paper",
                mode=mode,
                endpoint="api.binance.com",
                status=status,
                eligibility="NONE",
                is_active=True,
            )
        )

    with migrated_uow.session() as session:
        view = build_active_account_view(session)
        snap = build_dashboard_snapshot(session, now=NOW, adapter_connected=True)

    assert view.is_ready is expect_ready
    assert view.mode_allowed is expect_allowed
    if not expect_ready:
        assert snap.is_trading_blocked is True
    if not expect_allowed:
        assert "MODE NOT PERMITTED" in view.banner


@pytest.mark.d1c
def test_live_account_with_valid_cert_is_still_refused(migrated_uow: UnitOfWork) -> None:
    """Even a valid D1b certificate must not make LIVE tradable."""
    with migrated_uow.session() as session:
        session.add(
            Account(
                account_id="live1",
                adapter_id="ccxt",
                mode="LIVE",
                endpoint="api.binance.com",
                status="READY",
                eligibility="DEMO_CERTIFIED",
                is_active=True,
            )
        )
        session.add(
            CertificationRecord(
                cert_id="cert-ok",
                tuple_key="binance|spot|binance_spot_testnet|BTC/USDT|15m",
                valid=True,
            )
        )

    with migrated_uow.session() as session:
        view = build_active_account_view(session)

    assert view.cert_valid is True
    assert view.is_ready is False
    assert view.mode_allowed is False


@pytest.mark.parametrize(
    ("timeframe", "expected"),
    [
        ("15m", 900),
        ("1h", 3600),
        ("30s", 30),
        ("1d", 86400),
        ("15M", 900),
        ("0m", None),
        ("abc", None),
        ("m", None),
        ("", None),
        (None, None),
    ],
)
@pytest.mark.d1c
def test_parse_timeframe_seconds(timeframe: str | None, expected: int | None) -> None:
    assert parse_timeframe_seconds(timeframe) == expected


@pytest.mark.d1c
def test_data_age_is_measured_from_candle_close_not_open(
    migrated_uow: UnitOfWork,
) -> None:
    """A 15m candle that just closed is 0s old, not 900s."""
    with migrated_uow.session() as session:
        _seed_account(session)
        session.add(
            MarketCandle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time=NOW - timedelta(seconds=900),
                open=d("1"),
                high=d("1"),
                low=d("1"),
                close=d("1"),
                volume=d("1"),
                is_closed=True,
            )
        )

    with migrated_uow.session() as session:
        snap = build_dashboard_snapshot(session, now=NOW)

    assert snap.data_age_sec == pytest.approx(0.0)


@pytest.mark.d1c
def test_live_monitor_never_hides_inflight_intents(migrated_uow: UnitOfWork) -> None:
    """Regression: LIMIT ran before the UNKNOWN-first sort.

    With 250 intents and the 10 UNKNOWN ones inserted last, the old code
    returned 200 settled rows and zero UNKNOWN — hiding exactly what the
    operator must act on.
    """
    with migrated_uow.session() as session:
        _seed_account(session)
        for i in range(250):
            state = (
                IntentState.UNKNOWN.value if i >= 240 else IntentState.FILLED.value
            )
            session.add(
                OrderIntent(
                    intent_id=f"i{i:04d}",
                    client_order_id=f"c{i:04d}",
                    state=state,
                    account_id="paper1",
                    side="buy",
                    qty=d("1"),
                    symbol="BTC/USDT",
                )
            )

    with migrated_uow.session() as session:
        page = build_live_monitor_page(session, account_id="paper1")

    assert page.total == 250
    assert page.inflight_total == 10
    assert len(page.attention_rows) == 10
    assert {r.intent_id for r in page.attention_rows} == {
        f"i{i:04d}" for i in range(240, 250)
    }
    # In-flight rows come first and do not eat the settled budget.
    assert [r.needs_attention for r in page.rows[:10]] == [True] * 10
    assert len(page.rows) == DEFAULT_LIVE_MONITOR_LIMIT
    assert page.truncated == 50
    assert page.has_more is True


@pytest.mark.d1c
def test_live_monitor_returns_all_inflight_even_beyond_the_limit(
    migrated_uow: UnitOfWork,
) -> None:
    """`limit` caps settled padding only — in-flight is never sacrificed."""
    with migrated_uow.session() as session:
        _seed_account(session)
        for i in range(12):
            session.add(
                OrderIntent(
                    intent_id=f"u{i:03d}",
                    client_order_id=f"cu{i:03d}",
                    state=IntentState.UNKNOWN.value,
                    account_id="paper1",
                    side="sell",
                    qty=d("1"),
                    symbol="BTC/USDT",
                )
            )

    with migrated_uow.session() as session:
        page = build_live_monitor_page(session, account_id="paper1", limit=5)

    assert len(page.rows) == 12
    assert page.inflight_total == 12
    assert page.truncated == 0


@pytest.mark.d1c
def test_live_monitor_empty_database(migrated_uow: UnitOfWork) -> None:
    with migrated_uow.session() as session:
        page = build_live_monitor_page(session)
    assert page.rows == []
    assert page.total == 0
    assert page.has_more is False


@pytest.mark.d1c
def test_live_monitor_rejects_negative_limit(migrated_uow: UnitOfWork) -> None:
    with migrated_uow.session() as session, pytest.raises(ValueError):
        build_live_monitor_page(session, limit=-1)


@pytest.mark.d1c
def test_live_monitor_surfaces_unknown_first(migrated_uow: UnitOfWork) -> None:
    with migrated_uow.session() as session:
        _seed_account(session)
        session.add(
            OrderIntent(
                intent_id="i-filled",
                client_order_id="c-filled",
                state=IntentState.FILLED.value,
                account_id="paper1",
                side="buy",
                qty=d("1"),
                symbol="BTC/USDT",
            )
        )
        session.add(
            OrderIntent(
                intent_id="i-unknown",
                client_order_id="c-unknown",
                state=IntentState.UNKNOWN.value,
                account_id="paper1",
                side="sell",
                qty=d("2"),
                symbol="BTC/USDT",
            )
        )
        session.add(
            Order(
                intent_id="i-unknown",
                broker_order_id=None,
                delivery_certainty=DeliveryCertainty.MAY_HAVE_BEEN_ACCEPTED.value,
                state=IntentState.UNKNOWN.value,
            )
        )

    with migrated_uow.session() as session:
        page = build_live_monitor_page(session, account_id="paper1")

    rows = page.rows
    assert [r.intent_id for r in rows] == ["i-unknown", "i-filled"]
    assert rows[0].needs_attention is True
    assert rows[0].delivery_certainty == DeliveryCertainty.MAY_HAVE_BEEN_ACCEPTED.value
    assert rows[1].needs_attention is False
    assert page.total == 2
    assert page.truncated == 0


@pytest.mark.d1c
def test_live_monitor_settled_rows_are_ordered_most_recent_first(
    migrated_uow: UnitOfWork,
) -> None:
    """T041: settled rows order by `created_at` desc, not the random UUID.

    `intent_id` is a random UUID, so inserting "oldest" first with an
    alphabetically-later id proves the sort key really is `created_at`, not
    an accidental match with insertion/id order.
    """
    with migrated_uow.session() as session:
        _seed_account(session)
        session.add(
            OrderIntent(
                intent_id="z-oldest",
                client_order_id="c-oldest",
                state=IntentState.FILLED.value,
                account_id="paper1",
                side="buy",
                qty=d("1"),
                symbol="BTC/USDT",
                created_at=NOW - timedelta(hours=2),
            )
        )
        session.add(
            OrderIntent(
                intent_id="a-newest",
                client_order_id="c-newest",
                state=IntentState.FILLED.value,
                account_id="paper1",
                side="sell",
                qty=d("2"),
                symbol="BTC/USDT",
                created_at=NOW,
            )
        )
        session.add(
            OrderIntent(
                intent_id="m-middle",
                client_order_id="c-middle",
                state=IntentState.FILLED.value,
                account_id="paper1",
                side="buy",
                qty=d("3"),
                symbol="BTC/USDT",
                created_at=NOW - timedelta(hours=1),
            )
        )

    with migrated_uow.session() as session:
        page = build_live_monitor_page(session, account_id="paper1")

    assert [r.intent_id for r in page.rows] == ["a-newest", "m-middle", "z-oldest"]
    assert page.rows[0].created_at == NOW
    assert page.rows[1].created_at == NOW - timedelta(hours=1)
    assert page.rows[2].created_at == NOW - timedelta(hours=2)


@pytest.mark.d1c
def test_live_monitor_inflight_rows_are_also_ordered_most_recent_first(
    migrated_uow: UnitOfWork,
) -> None:
    """In-flight rows are always all returned; recency ordering among them
    is still more useful to the operator than random UUID order."""
    with migrated_uow.session() as session:
        _seed_account(session)
        session.add(
            OrderIntent(
                intent_id="z-old-unknown",
                client_order_id="c-old-unknown",
                state=IntentState.UNKNOWN.value,
                account_id="paper1",
                side="buy",
                qty=d("1"),
                symbol="BTC/USDT",
                created_at=NOW - timedelta(minutes=30),
            )
        )
        session.add(
            OrderIntent(
                intent_id="a-new-unknown",
                client_order_id="c-new-unknown",
                state=IntentState.UNKNOWN.value,
                account_id="paper1",
                side="sell",
                qty=d("1"),
                symbol="BTC/USDT",
                created_at=NOW,
            )
        )

    with migrated_uow.session() as session:
        page = build_live_monitor_page(session, account_id="paper1")

    assert [r.intent_id for r in page.rows] == ["a-new-unknown", "z-old-unknown"]
    assert page.inflight_total == 2


@pytest.mark.d1c
def test_live_monitor_row_created_at_is_populated(migrated_uow: UnitOfWork) -> None:
    with migrated_uow.session() as session:
        _seed_account(session)
        session.add(
            OrderIntent(
                intent_id="i-ts",
                client_order_id="c-ts",
                state=IntentState.FILLED.value,
                account_id="paper1",
                side="buy",
                qty=d("1"),
                symbol="BTC/USDT",
                created_at=NOW,
            )
        )

    with migrated_uow.session() as session:
        page = build_live_monitor_page(session, account_id="paper1")

    assert page.rows[0].created_at == NOW
