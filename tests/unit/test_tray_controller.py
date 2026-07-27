"""T011 — tray controller: Pause is never PIN-gated (no Qt required)."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from autotrade.app_ui.controllers import tray as tray_module
from autotrade.app_ui.controllers.tray import (
    PAUSE_AUDIT_TYPE,
    TrayController,
    format_money,
)
from autotrade.core.domain.money import d
from autotrade.persistence.models import (
    Account,
    AuditEvent,
    BalanceSnapshot,
    KillSwitchState,
)
from autotrade.persistence.uow import UnitOfWork

NOW = datetime(2026, 7, 27, 12, 30, tzinfo=UTC)


class FakeKillSwitch:
    """Minimal KillSwitchPort — records calls, never consults a PIN."""

    def __init__(self, level: int = 0) -> None:
        self.level = level
        self.latched = level > 0
        self.calls: list[str] = []
        self.persisted = 0

    def pause_l1(self, *, reason: str = "pause") -> None:
        self.calls.append(reason)
        if self.level < 1:
            self.level = 1
        self.latched = True

    def persist(self, session) -> None:  # noqa: ANN001 - Session
        self.persisted += 1


def _seed_account(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add(
            Account(
                account_id="paper1",
                adapter_id="paper",
                mode="PAPER",
                endpoint="local",
                status="READY",
                eligibility="ELIGIBLE",
                is_active=True,
            )
        )


@pytest.mark.d1c
def test_pause_uses_injected_kill_switch_without_any_pin(migrated_uow: UnitOfWork) -> None:
    fake = FakeKillSwitch()
    controller = TrayController(
        migrated_uow, kill_switch_loader=lambda _s, _scope: fake
    )

    result = controller.pause()

    assert fake.calls == ["tray_pause"]
    assert fake.persisted == 1
    assert result.level == 1
    assert result.latched is True
    assert result.already_paused is False
    assert "Paused" in result.message


@pytest.mark.d1c
def test_pause_persists_kill_switch_state(migrated_uow: UnitOfWork) -> None:
    controller = TrayController(migrated_uow)

    controller.pause()

    with migrated_uow.session() as session:
        row = session.scalars(
            select(KillSwitchState).where(KillSwitchState.scope == "global")
        ).one()
        assert row.level == 1
        assert row.latched is True


@pytest.mark.d1c
def test_pause_is_idempotent_and_reports_already_paused(migrated_uow: UnitOfWork) -> None:
    controller = TrayController(migrated_uow)

    first = controller.pause()
    second = controller.pause()

    assert first.already_paused is False
    assert second.already_paused is True
    assert second.level == 1
    assert "Already paused" in second.message


@pytest.mark.d1c
def test_pause_never_downgrades_a_higher_level(migrated_uow: UnitOfWork) -> None:
    with migrated_uow.session() as session:
        session.add(
            KillSwitchState(scope="global", level=3, triggers_json=None, latched=True)
        )

    result = TrayController(migrated_uow).pause()

    assert result.level == 3
    assert result.already_paused is True
    with migrated_uow.session() as session:
        row = session.scalars(
            select(KillSwitchState).where(KillSwitchState.scope == "global")
        ).one()
        assert row.level == 3


@pytest.mark.d1c
def test_pause_writes_an_audit_event(migrated_uow: UnitOfWork) -> None:
    TrayController(migrated_uow).pause(reason="operator_panic")

    with migrated_uow.session() as session:
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.type == PAUSE_AUDIT_TYPE)
        ).all()
    assert len(events) == 1
    assert events[0].payload_redacted["reason"] == "operator_panic"
    assert events[0].payload_redacted["level"] == 1


@pytest.mark.d1c
def test_tooltip_reports_account_and_kill_switch(migrated_uow: UnitOfWork) -> None:
    _seed_account(migrated_uow)
    controller = TrayController(migrated_uow, adapter_connected=lambda: True)

    controller.pause()
    text = controller.tooltip(now=NOW)

    assert "PAPER" in text
    assert "paper1" in text
    assert "KS L1" in text


@pytest.mark.d1c
def test_snapshot_passes_adapter_state_through(migrated_uow: UnitOfWork) -> None:
    _seed_account(migrated_uow)
    connected = TrayController(migrated_uow, adapter_connected=lambda: True)
    offline = TrayController(migrated_uow, adapter_connected=lambda: False)

    assert connected.snapshot(now=NOW).adapter_connected is True
    assert offline.snapshot(now=NOW).adapter_connected is False


#: Modules that would mean the tray path became PIN-gated. Matched exactly —
#: a substring check would flag "typing" for containing "pin".
PIN_MODULES = frozenset({"autotrade.persistence.pin"})


@pytest.mark.d1c
def test_tray_module_has_no_pin_dependency() -> None:
    """Static guard: a PIN import here would be a contract regression."""
    source = Path(tray_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(a.name for a in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    assert PIN_MODULES.isdisjoint(modules), sorted(set(modules) & PIN_MODULES)
    assert "verify_pin" not in source


@pytest.mark.d1c
def test_decimal_helper_is_available_for_fixtures() -> None:
    # Guards the money helper the seeds rely on (Decimal, never float).
    assert d("1.5") + d("0.5") == d("2.0")


@pytest.mark.parametrize(
    ("raw", "signed", "expected"),
    [
        (d("1123.500000000000"), False, "1123.50"),
        (d("1123.500000000000"), True, "+1123.50"),
        (d("-42.000000000000"), True, "-42.00"),
        (d("0.000000000000"), True, "+0.00"),
        (d("1.005"), False, "1.00"),  # banker's rounding, not float drift
        (None, False, "—"),
    ],
)
@pytest.mark.d1c
def test_format_money_quantises_for_display(raw, signed, expected) -> None:  # noqa: ANN001
    assert format_money(raw, signed=signed) == expected


@pytest.mark.d1c
def test_tooltip_does_not_leak_numeric_24_12_zero_tails(
    migrated_uow: UnitOfWork,
) -> None:
    """Regression: Numeric(24, 12) rendered as '1123.500000000000'.

    `:g` strips trailing zeros on float but NOT on Decimal, which honours its
    own exponent — the value must be quantised instead.
    """
    _seed_account(migrated_uow)
    with migrated_uow.session() as session:
        session.add(
            BalanceSnapshot(
                account_id="paper1",
                equity=d("1123.5"),
                ts=NOW.replace(hour=0, minute=1),
                source="paper",
            )
        )

    text = TrayController(migrated_uow).tooltip(now=NOW)

    assert "Equity 1123.50 " in text
    assert "000000" not in text
