"""T030 — Broker Hub read model, Qt-free.

Mirrors `data-model.md`'s `BrokerHubState` shape (paper_account?, demo_account?,
capabilities_redacted?, last_test_at?, last_error_redacted?). No mutation and
no `ccxt` import here — see `specs/003-d1c-desktop-mvp/contracts/ui-core-boundary.md`.

The "last test connection" fields have no dedicated table; they are read back
from the `audit_events` row `BrokerHubController.test_connection` writes
(`TEST_CONNECTION_AUDIT_TYPE`), the same pattern `tray.py` uses for Pause.
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


def build_broker_hub_state(session: Session) -> BrokerHubState:
    """Assemble the Broker Hub read model. No mutation, no ccxt."""
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
    if last_event is not None:
        last_test_at = last_event.at
        payload = last_event.payload_redacted or {}
        capabilities = payload.get("capabilities")
        last_error = payload.get("error")

    return BrokerHubState(
        paper_account=_account_summary(paper),
        demo_account=_account_summary(demo),
        cert_valid=cert_valid,
        capabilities_redacted=capabilities,
        last_test_at=last_test_at,
        last_error_redacted=last_error,
    )
