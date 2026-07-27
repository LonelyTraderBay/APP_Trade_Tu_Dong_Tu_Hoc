"""T010 — MainWindow + navigation shell (empty pages).

Pages are deliberately placeholders: Phase 2 only proves the shell opens,
navigates and shows the mode/account/endpoint banner. The trading screens
land in Phase 3 behind the D1b certification gate.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from autotrade.app_ui.controllers.broker_hub import BrokerHubController
from autotrade.app_ui.controllers.history import HistoryController
from autotrade.app_ui.controllers.live_monitor import LiveMonitorController
from autotrade.app_ui.controllers.settings import SettingsController
from autotrade.app_ui.controllers.strategy import StrategyController
from autotrade.app_ui.controllers.tray import TrayController
from autotrade.app_ui.services.screens import SCREENS, ScreenSpec
from autotrade.app_ui.views.broker_hub_page import BrokerHubPage
from autotrade.app_ui.views.history_page import HistoryPage
from autotrade.app_ui.views.kill_switch_page import KillSwitchPage
from autotrade.app_ui.views.live_monitor_page import LiveMonitorPage
from autotrade.app_ui.views.settings_page import SettingsPage
from autotrade.app_ui.views.strategy_page import StrategyPage

WINDOW_TITLE = "AutoTrade AI — Desktop Solo"


class PlaceholderPage(QWidget):
    """Empty page for a screen whose widgets are not in this phase yet."""

    def __init__(self, spec: ScreenSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec

        title = QLabel(spec.title)
        title.setObjectName("pageTitle")
        font = title.font()
        font.setPointSize(font.pointSize() + 6)
        font.setBold(True)
        title.setFont(font)

        summary = QLabel(spec.summary)
        summary.setWordWrap(True)

        pending = QLabel(f"Not implemented yet — planned in task {spec.implemented_by}.")
        pending.setObjectName("pagePending")
        pending.setEnabled(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(summary)
        layout.addWidget(pending)
        layout.addStretch(1)


class MainWindow(QMainWindow):
    """Navigation shell: screen list on the left, stacked pages on the right."""

    def __init__(
        self,
        controller: TrayController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1024, 680)

        self.banner = QLabel("")
        self.banner.setObjectName("modeBanner")
        self.banner.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        self.nav.setFixedWidth(200)

        self.pages = QStackedWidget()
        self.pages.setObjectName("pageStack")

        for spec in SCREENS:
            item = QListWidgetItem(spec.title)
            item.setData(Qt.ItemDataRole.UserRole, spec.key)
            self.nav.addItem(item)
            self.pages.addWidget(self._build_page(spec))

        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self.nav)
        body_layout.addWidget(self.pages, 1)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 8, 12, 12)
        root_layout.setSpacing(8)
        root_layout.addWidget(self.banner)
        root_layout.addWidget(body, 1)
        self.setCentralWidget(root)

        self.statusBar().showMessage("Shell only — trading screens land in Phase 3.")
        self.refresh_banner()

    def _build_page(self, spec: ScreenSpec) -> QWidget:
        """Real widget for implemented screens; `PlaceholderPage` otherwise.

        `broker_hub` (T030) was the first screen to graduate; `kill_switch`
        and `live_monitor` (T040/T041) follow the exact same pattern. All
        three fall back to the placeholder when no `TrayController` was
        supplied (e.g. the Qt-shell tests construct `MainWindow()` with no
        session), since there is then no `UnitOfWork` to build a page
        controller from.

        `kill_switch` is handed `self._controller` directly (not a new
        controller built from its `uow`) so its Pause button runs the exact
        same `TrayController.pause()` the tray menu uses — one audit-event/
        idempotency implementation, not two.

        `strategy` (T050), `history` (T051) and `settings` (T052/T053)
        follow the same "new controller from the shared `uow`" pattern as
        `broker_hub`/`live_monitor` — none of them need to share mutable
        state with the tray, unlike `kill_switch`.
        """
        if spec.key == "broker_hub" and self._controller is not None:
            return BrokerHubPage(BrokerHubController(self._controller.uow))
        if spec.key == "kill_switch" and self._controller is not None:
            return KillSwitchPage(self._controller)
        if spec.key == "live_monitor" and self._controller is not None:
            return LiveMonitorPage(LiveMonitorController(self._controller.uow))
        if spec.key == "strategy" and self._controller is not None:
            return StrategyPage(StrategyController(self._controller.uow))
        if spec.key == "history" and self._controller is not None:
            return HistoryPage(HistoryController(self._controller.uow))
        if spec.key == "settings" and self._controller is not None:
            return SettingsPage(SettingsController(self._controller.uow))
        return PlaceholderPage(spec)

    def current_screen_key(self) -> str:
        item = self.nav.currentItem()
        return "" if item is None else str(item.data(Qt.ItemDataRole.UserRole))

    def show_screen(self, key: str) -> bool:
        for row in range(self.nav.count()):
            if self.nav.item(row).data(Qt.ItemDataRole.UserRole) == key:
                self.nav.setCurrentRow(row)
                return True
        return False

    def refresh_banner(self) -> None:
        """Mode/account/endpoint text — required on trade-capable screens."""
        if self._controller is None:
            self.banner.setText("PAPER · no session · local")
            return
        try:
            snapshot = self._controller.snapshot()
        except Exception as exc:  # noqa: BLE001 - banner must never crash the shell
            self.banner.setText(f"Session unavailable — {type(exc).__name__}")
            return
        self.banner.setText(snapshot.account.banner)
