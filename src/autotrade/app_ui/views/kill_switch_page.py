"""T040/T042 — Kill-switch page: L1-L4 display + Pause (no PIN) + Flatten.

Contract (`contracts/ui-core-boundary.md`): `pause_l1` / tray Pause is
**never PIN-gated** and must always be available — a lockout must not be
able to trap the operator with a running strategy. `flatten_local` is also
**no PIN**, but — unlike Pause — is "Confirm dialog only": a manual close
submits a real order, so this screen requires an explicit Yes/No confirm
before `KillSwitchController.flatten()` ever runs.

This page is handed the shell's existing `TrayController` and calls its
`.pause()` / `.snapshot()` directly rather than owning a second controller
that re-implements the same audit-event + idempotency logic. `MainWindow`
already threads one `TrayController` through the app (for the tray menu and
the mode/account/endpoint banner); sharing that instance here means the
Pause path executed from this screen is byte-for-byte the same code the
tray menu's Pause runs, so there is exactly one place that can regress the
no-PIN invariant.

Flatten is wired to a separate, small `KillSwitchController` (T042) — see
that module's docstring for why it is not folded into `TrayController` or
`BrokerHubController`. It defaults to sharing the same `TrayController.uow`
so both controllers read/write the same database.

L2-L4 are read-only on this screen: the codebase currently only exposes
manual triggers for L1 (Pause) and the reduce-only close (Flatten) — L2-L4
are system-escalated per the architecture doc, not manually user-triggered
here (tasks.md T040/T042).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from autotrade.app_ui.controllers.kill_switch import FlattenUiResult, KillSwitchController
from autotrade.app_ui.controllers.tray import PauseResult, TrayController

PAUSE_REASON = "kill_switch_page_pause"
FLATTEN_CONFIRM_TEXT = (
    "This will submit a closing order for the active account's position. Continue?"
)


def _format_triggers(triggers: dict[str, Any] | None) -> str:
    if not triggers:
        return "—"
    return ", ".join(f"{key}={value}" for key, value in sorted(triggers.items()))


class KillSwitchPage(QWidget):
    """Kill-switch screen: L1-L4 display + Pause (no PIN, always available)."""

    def __init__(
        self,
        controller: TrayController,
        *,
        flatten_controller: KillSwitchController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("killSwitchPage")
        self._controller = controller
        self._flatten_controller = flatten_controller or KillSwitchController(controller.uow)

        title = QLabel("Kill-switch")
        title.setObjectName("pageTitle")
        font = title.font()
        font.setPointSize(font.pointSize() + 6)
        font.setBold(True)
        title.setFont(font)

        # --- Status card -----------------------------------------------
        self.status_card = QGroupBox("Status")
        self.status_card.setObjectName("ksStatusCard")
        self.level_label = QLabel("")
        self.level_label.setObjectName("ksLevelLabel")
        self.latched_label = QLabel("")
        self.latched_label.setObjectName("ksLatchedLabel")
        self.triggers_label = QLabel("")
        self.triggers_label.setObjectName("ksTriggersLabel")
        self.triggers_label.setWordWrap(True)
        self.scale_note = QLabel(
            "L2-L4 are raised automatically by the system, not from this screen."
        )
        self.scale_note.setObjectName("ksScaleNote")
        self.scale_note.setWordWrap(True)
        self.scale_note.setEnabled(False)

        status_layout = QVBoxLayout(self.status_card)
        status_layout.addWidget(self.level_label)
        status_layout.addWidget(self.latched_label)
        status_layout.addWidget(self.triggers_label)
        status_layout.addWidget(self.scale_note)

        # --- Pause card ----------------------------------------------------
        self.pause_card = QGroupBox("Pause")
        self.pause_card.setObjectName("ksPauseCard")
        self.pause_button = QPushButton("Pause (raise to L1)")
        self.pause_button.setObjectName("pauseButton")
        self.pause_button.clicked.connect(self._on_pause)
        self.pause_result_label = QLabel("")
        self.pause_result_label.setObjectName("pauseResultLabel")
        self.pause_result_label.setWordWrap(True)

        pause_layout = QVBoxLayout(self.pause_card)
        pause_layout.addWidget(self.pause_button)
        pause_layout.addWidget(self.pause_result_label)

        # --- Flatten card (T042) --------------------------------------
        self.flatten_card = QGroupBox("Flatten")
        self.flatten_card.setObjectName("ksFlattenCard")
        self.flatten_button = QPushButton("Flatten position")
        self.flatten_button.setObjectName("flattenButton")
        self.flatten_button.clicked.connect(self._on_flatten)
        self.flatten_result_label = QLabel("")
        self.flatten_result_label.setObjectName("flattenResultLabel")
        self.flatten_result_label.setWordWrap(True)

        flatten_layout = QVBoxLayout(self.flatten_card)
        flatten_layout.addWidget(self.flatten_button)
        flatten_layout.addWidget(self.flatten_result_label)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(separator)
        layout.addWidget(self.status_card)
        layout.addWidget(self.pause_card)
        layout.addWidget(self.flatten_card)
        layout.addStretch(1)

        self.refresh()

    # --- state -----------------------------------------------------------

    def refresh(self) -> None:
        """Re-read the controller snapshot and repaint the status card."""
        try:
            snapshot = self._controller.snapshot()
        except Exception as exc:  # noqa: BLE001 - a snapshot must never crash the page
            self.level_label.setText(f"Session unavailable — {type(exc).__name__}")
            self.latched_label.setText("")
            self.triggers_label.setText("")
            return
        self._render(
            level=snapshot.ks_level,
            latched=snapshot.ks_latched,
            triggers=snapshot.ks_triggers,
        )

    def _render(self, *, level: int, latched: bool, triggers: dict[str, Any] | None) -> None:
        self.level_label.setText(
            f"Level: L{level}" if level > 0 else "Level: 0 (not triggered)"
        )
        self.latched_label.setText(f"Latched: {'yes' if latched else 'no'}")
        self.triggers_label.setText(
            f"Trigger: {_format_triggers(triggers)}" if latched else "Trigger: —"
        )

    # --- actions -----------------------------------------------------------

    def _on_pause(self) -> None:
        """No PIN, no confirmation dialog — a hard safety invariant.

        `TrayController.pause()` is idempotent and always available; nothing
        in this handler can refuse or block it before it runs.
        """
        result: PauseResult = self._controller.pause(reason=PAUSE_REASON)
        self.refresh()
        self.pause_result_label.setText(result.message)

    def _on_flatten(self) -> None:
        """Confirm-dialog-only, no PIN (contract: `flatten_local`).

        Unlike Pause, this submits a real closing order — the operator must
        explicitly confirm before `KillSwitchController.flatten()` runs.
        Answering anything but Yes is a hard no-op: no controller call, no
        order.
        """
        answer = QMessageBox.question(
            self,
            "Confirm flatten",
            FLATTEN_CONFIRM_TEXT,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            result: FlattenUiResult = self._flatten_controller.flatten()
        except Exception as exc:  # noqa: BLE001 - a flatten must never crash the page
            self.flatten_result_label.setText(f"Flatten unavailable — {type(exc).__name__}")
            QMessageBox.critical(self, "Flatten failed", f"Unexpected error: {exc}")
            return

        self.flatten_result_label.setText(result.message)
        if result.ok:
            QMessageBox.information(self, "Flatten submitted", result.message)
        else:
            QMessageBox.warning(self, "Flatten failed", result.message)
