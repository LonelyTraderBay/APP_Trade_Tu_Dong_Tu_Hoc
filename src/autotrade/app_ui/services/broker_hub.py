"""T030 — Broker Hub read model, Qt-free.

Mirrors `data-model.md`'s `BrokerHubState` shape (paper_account?, demo_account?,
capabilities_redacted?, last_test_at?, last_error_redacted?). No mutation and
no `ccxt` import here — see `specs/003-d1c-desktop-mvp/contracts/ui-core-boundary.md`.

The "last test connection" fields have no dedicated table; they are read back
from the `audit_events` row `BrokerHubController.test_connection` writes
(`TEST_CONNECTION_AUDIT_TYPE`), the same pattern `tray.py` uses for Pause.

`demo_credentials_configured` (G1.2/G7 "tự kết nối") follows the exact
"controller computes presence via keyring, read model only carries the
bool" split `SettingsController.telegram_configured()` /
`build_settings_view(..., telegram_configured=...)` established — this file
never imports `persistence.secrets`/`keyring` itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from autotrade.core.certify.records import get_cert
from autotrade.persistence.models import Account, AuditEvent

#: Audit event type written by `BrokerHubController.test_connection` — the
#: read model looks up the latest row of this type for last_test_at etc.
TEST_CONNECTION_AUDIT_TYPE = "ui.broker_hub.test_connection"


@dataclass(frozen=True, slots=True)
class BrokerAccountSummary:
    """One row for the Paper or DEMO card."""

    account_id: str
    mode: str
    endpoint_class: str | None
    status: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class BrokerHubState:
    """Everything the Broker Hub screen renders, in one immutable read."""

    paper_account: BrokerAccountSummary | None
    demo_account: BrokerAccountSummary | None
    cert_valid: bool
    capabilities_redacted: dict[str, Any] | None
    last_test_at: datetime | None
    last_error_redacted: str | None
    #: Presence-only — never the key/secret values (G1.2/G7 "tự kết nối").
    demo_credentials_configured: bool
    #: G7 step 5 VERIFIED/DENIED/UNKNOWN verdict from the last test, if any.
    last_verdict: str | None = None

    @property
    def can_enable_demo(self) -> bool:
        """Mirrors `assert_cert_valid_for_trading` — the gate the controller enforces."""
        return self.cert_valid

    @property
    def cert_gate_reason(self) -> str:
        """Tooltip text for a disabled Enable-DEMO button."""
        if self.cert_valid:
            return "Certification valid — DEMO can be enabled."
        return (
            "Certification not valid — complete the D1b contract/fault/"
            "lifecycle/soak gates before DEMO can be enabled."
        )

    @property
    def demo_ready_for_connection(self) -> bool:
        """Whether Test connection / Enable DEMO have what they need: either
        an already-provisioned DEMO account, or credentials stored in the
        keyring ready to provision one (G1.2/G7 precondition)."""
        return self.demo_account is not None or self.demo_credentials_configured

    @property
    def credentials_gate_reason(self) -> str:
        """Tooltip text when Test connection / Enable DEMO are blocked on
        missing credentials — same setEnabled/setToolTip idiom as
        `cert_gate_reason`, not a second disabled-state mechanism."""
        if self.demo_ready_for_connection:
            return "DEMO credentials configured."
        return (
            "Store DEMO API credentials first (below) before testing or"
            " enabling DEMO."
        )


def _account_summary(account: Account | None) -> BrokerAccountSummary | None:
    if account is None:
        return None
    return BrokerAccountSummary(
        account_id=account.account_id,
        mode=account.mode,
        endpoint_class=account.endpoint,
        status=account.status,
        is_active=account.is_active,
    )


def build_broker_hub_state(
    session: Session, *, demo_credentials_configured: bool
) -> BrokerHubState:
    """Assemble the Broker Hub read model. No mutation, no ccxt.

    `demo_credentials_configured` is computed by the controller (keyring
    presence check) and passed in — same split as
    `build_settings_view(..., telegram_configured=...)`.
    """
    paper = session.query(Account).filter_by(mode="PAPER").first()
    demo = session.query(Account).filter_by(mode="DEMO").first()
    cert = get_cert(session)
    cert_valid = bool(cert is not None and cert.valid)

    last_event = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.type == TEST_CONNECTION_AUDIT_TYPE)
        .order_by(AuditEvent.at.desc())
    ).first()

    capabilities: dict[str, Any] | None = None
    last_error: str | None = None
    last_test_at: datetime | None = None
    last_verdict: str | None = None
    if last_event is not None:
        last_test_at = last_event.at
        payload = last_event.payload_redacted or {}
        capabilities = payload.get("capabilities")
        last_error = payload.get("error")
        last_verdict = payload.get("verdict")

    return BrokerHubState(
        paper_account=_account_summary(paper),
        demo_account=_account_summary(demo),
        cert_valid=cert_valid,
        capabilities_redacted=capabilities,
        last_test_at=last_test_at,
        last_error_redacted=last_error,
        demo_credentials_configured=demo_credentials_configured,
        last_verdict=last_verdict,
    )
