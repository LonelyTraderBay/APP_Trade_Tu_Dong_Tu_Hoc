"""Certification record promote / invalidate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from autotrade.core.certify import records as cert
from autotrade.core.certify.invalidate import invalidate_on_change
from autotrade.core.certify.lifecycle import record_completed_lifecycle
from autotrade.core.domain.allowlist import D1B_ALLOWLIST


@pytest.mark.d1b
def test_cert_requires_all_gates(migrated_uow) -> None:  # noqa: ANN001
    with migrated_uow.session() as session:
        cert.mark_contract_passed(session)
        cert.mark_fault_passed(session)
        row = cert.try_promote_valid(session)
        assert row.valid is False
        for i in range(50):
            record_completed_lifecycle(
                session,
                account_id="demo1",
                source="real_testnet",
                notes=f"n={i}",
            )
        started = datetime.now(UTC) - timedelta(hours=72)
        ended = datetime.now(UTC)
        cert.mark_soak_passed(session, started_at=started, ended_at=ended)
        row = cert.try_promote_valid(session)
        assert row.valid is True
        assert row.tuple_key == D1B_ALLOWLIST.canonical_key


@pytest.mark.d1b
def test_mock_lifecycle_does_not_count(migrated_uow) -> None:  # noqa: ANN001
    with migrated_uow.session() as session:
        assert (
            record_completed_lifecycle(
                session, account_id="demo1", source="mock"
            )
            is None
        )


@pytest.mark.d1b
def test_invalidate_on_ccxt_change(migrated_uow) -> None:  # noqa: ANN001
    with migrated_uow.session() as session:
        cert.snapshot_versions(
            session,
            app_version="0.1.0a0",
            ccxt_version="4.4.0",
            endpoint_fingerprint="binance_spot_testnet",
            instrument_metadata_hash="abc",
        )
        row = cert.ensure_cert_row(session)
        row.valid = True
        session.add(row)
        invalidate_on_change(session, reason="", current_ccxt="4.5.0")
        row = cert.get_cert(session)
        assert row is not None
        assert row.valid is False
        assert row.invalidated_reason == "ccxt_version_changed"


@pytest.mark.d1b
def test_invalidate_records_all_change_reasons(migrated_uow) -> None:  # noqa: ANN001
    with migrated_uow.session() as session:
        cert.snapshot_versions(
            session,
            app_version="0.1.0a0",
            ccxt_version="4.4.0",
            endpoint_fingerprint="fp-old",
            instrument_metadata_hash="hash-old",
        )
        row = cert.ensure_cert_row(session)
        row.valid = True
        session.add(row)
        invalidate_on_change(
            session,
            reason="",
            current_ccxt="4.5.0",
            current_endpoint_fp="fp-new",
            current_instrument_hash="hash-new",
            current_app="0.1.0a1",
        )
        row = cert.get_cert(session)
        assert row is not None
        assert row.valid is False
        assert row.invalidated_reason is not None
        assert "ccxt_version_changed" in row.invalidated_reason
        assert "endpoint_fingerprint_changed" in row.invalidated_reason
        assert "instrument_metadata_changed" in row.invalidated_reason
        assert "app_version_changed" in row.invalidated_reason
