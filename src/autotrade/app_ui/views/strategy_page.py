"""T050 — Strategy page: rule_sma_cross_v1 params, read-only hard ceilings.

Contract (tasks.md T050, `contracts/screens.md`): this screen is **read-only
display only**. Every widget here is a `QLabel` — there is deliberately no
`QLineEdit`/`QComboBox`/`QCheckBox`/`QSpinBox` or any other editable input,
because "read-only" is explicit in the task name and the hard ceilings
(`D1B_ALLOWLIST`) are Owner-locked immutable data
(`core/domain/allowlist.py`'s own docstring). Do not add an editable widget
to this page, even a disabled one that looks editable — the zero-editable-
widgets invariant is asserted by `tests/integration/test_strategy_ui.py`.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from autotrade.app_ui.controllers.strategy import StrategyController
from autotrade.app_ui.services.strategy import StrategyView


def _format_params(params: dict) -> str:
    if not params:
        return "(none)"
    return ", ".join(f"{key}={value}" for key, value in sorted(params.items()))


class StrategyPage(QWidget):
    """Strategy screen: binding summary + locked hard ceilings, no editing."""

    def __init__(
        self, controller: StrategyController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("strategyPage")
        self._controller = controller

        title = QLabel("Strategy")
        title.setObjectName("pageTitle")
        font = title.font()
        font.setPointSize(font.pointSize() + 6)
        font.setBold(True)
        title.setFont(font)

        # --- Binding card (read-only) --------------------------------------
        self.binding_card = QGroupBox("rule_sma_cross_v1")
        self.binding_card.setObjectName("bindingCard")
        self.strategy_id_label = QLabel("")
        self.strategy_id_label.setObjectName("strategyIdLabel")
        self.symbol_label = QLabel("")
        self.symbol_label.setObjectName("symbolLabel")
        self.timeframe_label = QLabel("")
        self.timeframe_label.setObjectName("timeframeLabel")
        self.params_label = QLabel("")
        self.params_label.setObjectName("paramsLabel")
        self.params_label.setWordWrap(True)
        self.enabled_label = QLabel("")
        self.enabled_label.setObjectName("enabledLabel")
        self.binding_status_label = QLabel("")
        self.binding_status_label.setObjectName("bindingStatusLabel")
        self.binding_status_label.setWordWrap(True)
        self.binding_status_label.setEnabled(False)

        binding_layout = QVBoxLayout(self.binding_card)
        binding_layout.addWidget(self.strategy_id_label)
        binding_layout.addWidget(self.symbol_label)
        binding_layout.addWidget(self.timeframe_label)
        binding_layout.addWidget(self.params_label)
        binding_layout.addWidget(self.enabled_label)
        binding_layout.addWidget(self.binding_status_label)

        # --- Hard ceilings card (locked, read-only) -------------------------
        self.ceiling_card = QGroupBox("Hard ceilings (Owner-locked, read-only)")
        self.ceiling_card.setObjectName("ceilingCard")
        self.ceiling_exchange_label = QLabel("")
        self.ceiling_exchange_label.setObjectName("ceilingExchangeLabel")
        self.ceiling_market_label = QLabel("")
        self.ceiling_market_label.setObjectName("ceilingMarketLabel")
        self.ceiling_endpoint_label = QLabel("")
        self.ceiling_endpoint_label.setObjectName("ceilingEndpointLabel")
        self.ceiling_symbol_label = QLabel("")
        self.ceiling_symbol_label.setObjectName("ceilingSymbolLabel")
        self.ceiling_timeframe_label = QLabel("")
        self.ceiling_timeframe_label.setObjectName("ceilingTimeframeLabel")
        self.ceiling_note = QLabel(
            "These values cannot be changed from the UI — they are certified"
            " in D1b and locked at the code level."
        )
        self.ceiling_note.setObjectName("ceilingNote")
        self.ceiling_note.setWordWrap(True)
        self.ceiling_note.setEnabled(False)

        ceiling_layout = QVBoxLayout(self.ceiling_card)
        ceiling_layout.addWidget(self.ceiling_exchange_label)
        ceiling_layout.addWidget(self.ceiling_market_label)
        ceiling_layout.addWidget(self.ceiling_endpoint_label)
        ceiling_layout.addWidget(self.ceiling_symbol_label)
        ceiling_layout.addWidget(self.ceiling_timeframe_label)
        ceiling_layout.addWidget(self.ceiling_note)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(separator)
        layout.addWidget(self.binding_card)
        layout.addWidget(self.ceiling_card)
        layout.addStretch(1)

        self.refresh()

    # --- state ---------------------------------------------------------

    def refresh(self) -> None:
        """Re-read the controller snapshot and repaint every label."""
        try:
            view = self._controller.snapshot()
        except Exception as exc:  # noqa: BLE001 - a snapshot must never crash the page
            self.strategy_id_label.setText(f"Session unavailable — {type(exc).__name__}")
            self.symbol_label.setText("")
            self.timeframe_label.setText("")
            self.params_label.setText("")
            self.enabled_label.setText("")
            self.binding_status_label.setText("")
            return
        self._render(view)

    def _render(self, view: StrategyView) -> None:
        self.strategy_id_label.setText(f"Strategy ID: {view.strategy_id}")
        self.symbol_label.setText(f"Symbol: {view.symbol}")
        self.timeframe_label.setText(f"Timeframe: {view.timeframe}")
        self.params_label.setText(f"Params: {_format_params(view.params)}")
        self.enabled_label.setText(f"Enabled: {'yes' if view.enabled else 'no'}")
        self.binding_status_label.setText(
            ""
            if view.binding_found
            else "No binding persisted yet — showing the allowlist default"
            " (Enable DEMO from Broker Hub creates the real binding)."
        )

        self.ceiling_exchange_label.setText(f"Exchange: {view.ceiling_exchange_id}")
        self.ceiling_market_label.setText(f"Market: {view.ceiling_market}")
        self.ceiling_endpoint_label.setText(f"Endpoint class: {view.ceiling_endpoint_class}")
        self.ceiling_symbol_label.setText(f"Symbol: {view.ceiling_symbol}")
        self.ceiling_timeframe_label.setText(f"Timeframe: {view.ceiling_timeframe}")
