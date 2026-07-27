"""T050 — Strategy read model: hard ceilings + binding projection, Qt-free."""

from __future__ import annotations

import pytest

from autotrade.app_ui.services.strategy import build_strategy_view
from autotrade.core.accounts.bindings import STRATEGY_ID, bind_demo_strategy
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.persistence.uow import UnitOfWork


@pytest.mark.d1c
def test_strategy_view_without_a_binding_falls_back_to_allowlist_defaults(
    migrated_uow: UnitOfWork,
) -> None:
    with migrated_uow.session() as session:
        view = build_strategy_view(session)

    assert view.binding_found is False
    assert view.strategy_id == STRATEGY_ID
    assert view.symbol == D1B_ALLOWLIST.symbol
    assert view.timeframe == D1B_ALLOWLIST.timeframe
    assert view.params == {}
    assert view.enabled is False


@pytest.mark.d1c
def test_strategy_view_reflects_a_persisted_binding(migrated_uow: UnitOfWork) -> None:
    with migrated_uow.session() as session:
        bind_demo_strategy(session, account_id="demo-binance")

    with migrated_uow.session() as session:
        view = build_strategy_view(session)

    assert view.binding_found is True
    assert view.symbol == D1B_ALLOWLIST.symbol
    assert view.timeframe == D1B_ALLOWLIST.timeframe
    assert view.enabled is True


@pytest.mark.d1c
def test_strategy_view_hard_ceilings_always_mirror_the_allowlist(
    migrated_uow: UnitOfWork,
) -> None:
    """The ceiling_* fields must never depend on binding state — they are
    the Owner-locked tuple, not editable/derived params."""
    with migrated_uow.session() as session:
        view = build_strategy_view(session)

    assert view.ceiling_exchange_id == D1B_ALLOWLIST.exchange_id
    assert view.ceiling_market == D1B_ALLOWLIST.market
    assert view.ceiling_endpoint_class == D1B_ALLOWLIST.endpoint_class
    assert view.ceiling_symbol == D1B_ALLOWLIST.symbol
    assert view.ceiling_timeframe == D1B_ALLOWLIST.timeframe


@pytest.mark.d1c
def test_strategy_view_filters_by_account_id_when_given(migrated_uow: UnitOfWork) -> None:
    with migrated_uow.session() as session:
        bind_demo_strategy(session, account_id="demo-binance")

    with migrated_uow.session() as session:
        view = build_strategy_view(session, account_id="some-other-account")

    assert view.binding_found is False
