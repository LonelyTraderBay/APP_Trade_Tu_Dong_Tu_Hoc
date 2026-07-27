"""T011 — system tray icon: status, Pause (no PIN), Open, Quit.

All behaviour lives in `TrayController`; this file only wires menu actions to
it so the logic stays testable without Qt.
"""

from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMainWindow, QMenu, QSystemTrayIcon, QWidget

from autotrade.app_ui.controllers.tray import TrayController

TRAY_TOOLTIP_FALLBACK = "AutoTrade AI — Desktop Solo"


class AppTray(QSystemTrayIcon):
    """Tray entry. Pause is always enabled — never gated behind the PIN."""

    def __init__(
        self,
        controller: TrayController,
        window: QMainWindow,
        *,
        icon: QIcon | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(icon or QIcon(), parent)
        self._controller = controller
        self._window = window

        menu = QMenu()
        self.open_action = QAction("Open AutoTrade", menu)
        self.open_action.triggered.connect(self.show_main_window)

        self.pause_action = QAction("Pause (kill-switch L1)", menu)
        self.pause_action.triggered.connect(self.pause)

        self.quit_action = QAction("Quit", menu)

        menu.addAction(self.open_action)
        menu.addAction(self.pause_action)
        menu.addSeparator()
        menu.addAction(self.quit_action)
        self.setContextMenu(menu)

        self.activated.connect(self._on_activated)
        self.refresh_tooltip()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_main_window()

    def show_main_window(self) -> None:
        self._window.showNormal()
        self._window.raise_()
        self._window.activateWindow()

    def pause(self) -> None:
        result = self._controller.pause()
        self.showMessage(
            "AutoTrade AI",
            result.message,
            QSystemTrayIcon.MessageIcon.Warning,
            5000,
        )
        self.refresh_tooltip()

    def refresh_tooltip(self) -> None:
        try:
            self.setToolTip(self._controller.tooltip())
        except Exception:  # noqa: BLE001 - a tooltip must never kill the tray
            self.setToolTip(TRAY_TOOLTIP_FALLBACK)
