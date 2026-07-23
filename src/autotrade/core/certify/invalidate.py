"""Invalidate certification when assumptions change."""

from __future__ import annotations

from sqlalchemy.orm import Session

from autotrade.core.certify import records as cert_records


def invalidate_on_change(
    session: Session,
    *,
    reason: str,
    current_ccxt: str | None = None,
    current_endpoint_fp: str | None = None,
    current_instrument_hash: str | None = None,
    current_app: str | None = None,
) -> None:
    row = cert_records.ensure_cert_row(session)
    changed = False
    if current_ccxt and row.ccxt_version and current_ccxt != row.ccxt_version:
        changed = True
        reason = reason or "ccxt_version_changed"
    if (
        current_endpoint_fp
        and row.endpoint_fingerprint
        and current_endpoint_fp != row.endpoint_fingerprint
    ):
        changed = True
        reason = "endpoint_fingerprint_changed"
    if (
        current_instrument_hash
        and row.instrument_metadata_hash
        and current_instrument_hash != row.instrument_metadata_hash
    ):
        changed = True
        reason = "instrument_metadata_changed"
    if current_app and row.app_version and current_app != row.app_version:
        changed = True
        reason = "app_version_changed"
    if changed or reason:
        cert_records.invalidate(
            session,
            reason=reason,
            ccxt_version=current_ccxt,
            endpoint_fingerprint=current_endpoint_fp,
            instrument_metadata_hash=current_instrument_hash,
            app_version=current_app,
        )
