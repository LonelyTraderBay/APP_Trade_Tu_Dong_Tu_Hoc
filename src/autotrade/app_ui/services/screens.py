"""Navigation registry for the D1c shell — Qt-free so CI can assert it.

Mirrors `specs/003-d1c-desktop-mvp/contracts/screens.md`. The Qt shell renders
whatever is listed here; keeping the list out of the view means the
screen-inventory contract is testable without PySide6 installed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScreenSpec:
    key: str
    title: str
    summary: str
    #: True when the screen can influence exposure and therefore MUST show the
    #: mode/account/endpoint banner (screens.md, last line).
    trade_capable: bool
    #: Task id that will fill this page in; empty shell until then.
    implemented_by: str


SCREENS: tuple[ScreenSpec, ...] = (
    ScreenSpec(
        key="dashboard",
        title="Dashboard",
        summary="Equity, PnL, kill-switch badge, health, data age.",
        trade_capable=True,
        implemented_by="T013",
    ),
    ScreenSpec(
        key="broker_hub",
        title="Broker Hub",
        summary="Paper/DEMO cards, Test connection, Enable DEMO (cert gate).",
        trade_capable=True,
        implemented_by="T030",
    ),
    ScreenSpec(
        key="kill_switch",
        title="Kill-switch",
        summary="L1–L4 display, Pause (no PIN), Flatten confirm.",
        trade_capable=True,
        implemented_by="T040",
    ),
    ScreenSpec(
        key="live_monitor",
        title="Live Monitor",
        summary="Orders/intents table including UNKNOWN. No blind-retry.",
        trade_capable=True,
        implemented_by="T041",
    ),
    ScreenSpec(
        key="strategy",
        title="Strategy",
        summary="rule_sma_cross_v1 params, read-only hard ceilings.",
        trade_capable=False,
        implemented_by="T050",
    ),
    ScreenSpec(
        key="history",
        title="History",
        summary="Filter by type/correlation id, redacted CSV export.",
        trade_capable=False,
        implemented_by="T051",
    ),
    ScreenSpec(
        key="settings",
        title="Settings",
        summary="PIN change, optional Telegram, allowlist read-only, backup.",
        trade_capable=False,
        implemented_by="T052",
    ),
)

SCREEN_KEYS: tuple[str, ...] = tuple(s.key for s in SCREENS)


def get_screen(key: str) -> ScreenSpec:
    for spec in SCREENS:
        if spec.key == key:
            return spec
    raise KeyError(f"unknown screen: {key}")
