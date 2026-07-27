"""T010 — navigation shell + screen inventory contract."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from autotrade.app_ui.services.screens import SCREEN_KEYS, SCREENS, get_screen

CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "specs"
    / "003-d1c-desktop-mvp"
    / "contracts"
    / "screens.md"
)

# The contract table also lists "Tray", which is not a navigable screen.
NON_SCREEN_ROWS = {"Tray", "Screen"}

TRADE_CAPABLE = {"dashboard", "broker_hub", "kill_switch", "live_monitor"}


def _contract_titles() -> list[str]:
    titles: list[str] = []
    for line in CONTRACT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        first = line.split("|")[1].strip()
        if not first or set(first) <= {"-", ":"} or first in NON_SCREEN_ROWS:
            continue
        titles.append(first)
    return titles


@pytest.mark.d1c
def test_registry_matches_screen_contract() -> None:
    assert [s.title for s in SCREENS] == _contract_titles()


@pytest.mark.d1c
def test_screen_keys_are_unique() -> None:
    assert len(set(SCREEN_KEYS)) == len(SCREEN_KEYS)


@pytest.mark.d1c
def test_trade_capable_screens_are_flagged() -> None:
    flagged = {s.key for s in SCREENS if s.trade_capable}
    assert flagged == TRADE_CAPABLE


@pytest.mark.d1c
def test_every_screen_declares_its_owning_task() -> None:
    for spec in SCREENS:
        assert spec.implemented_by.startswith("T"), spec


@pytest.mark.d1c
def test_get_screen_rejects_unknown_key() -> None:
    assert get_screen("dashboard").title == "Dashboard"
    with pytest.raises(KeyError):
        get_screen("nope")


# --- Qt-dependent shell checks (skipped when the [ui] extra is absent) ------


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201 - QApplication, only when PySide6 exists
    pytest.importorskip("PySide6", reason="optional extra [ui] not installed")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.mark.d1c
def test_main_window_lists_every_screen(qapp) -> None:  # noqa: ANN001
    from autotrade.app_ui.views.main_window import MainWindow

    window = MainWindow()
    try:
        assert window.nav.count() == len(SCREENS)
        assert window.pages.count() == len(SCREENS)
        assert window.current_screen_key() == "dashboard"
    finally:
        window.deleteLater()


@pytest.mark.d1c
def test_main_window_navigates_between_screens(qapp) -> None:  # noqa: ANN001
    from autotrade.app_ui.views.main_window import MainWindow

    window = MainWindow()
    try:
        assert window.show_screen("settings") is True
        assert window.current_screen_key() == "settings"
        assert window.pages.currentWidget().spec.key == "settings"
        assert window.show_screen("does_not_exist") is False
    finally:
        window.deleteLater()


@pytest.mark.d1c
def test_main_window_shows_banner_without_a_controller(qapp) -> None:  # noqa: ANN001
    from autotrade.app_ui.views.main_window import MainWindow

    window = MainWindow()
    try:
        assert window.banner.text() != ""
    finally:
        window.deleteLater()
