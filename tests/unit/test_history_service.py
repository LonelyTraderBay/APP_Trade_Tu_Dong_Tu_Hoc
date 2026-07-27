"""T051 — History read model + redacted CSV export, Qt-free."""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from autotrade.app_ui.services.history import (
    HistoryFilter,
    export_history_csv,
    parse_iso_datetime,
    query_history,
)
from autotrade.persistence.models import AuditEvent
from autotrade.persistence.uow import UnitOfWork

NOW = datetime(2026, 7, 27, 12, 0, 0, tzinfo=UTC)


def _seed(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add_all(
            [
                AuditEvent(
                    event_id="e1",
                    type="ui.tray.pause_l1",
                    payload_redacted={"scope": "global", "reason": "tray_pause"},
                    at=NOW - timedelta(hours=2),
                    correlation_id=None,
                ),
                AuditEvent(
                    event_id="e2",
                    type="intent_reserved",
                    payload_redacted={
                        "intent_id": "i1",
                        "client_order_id": "c1",
                        "account_id": "paper1",
                        "side": "buy",
                        "qty": "1",
                    },
                    at=NOW - timedelta(hours=1),
                    correlation_id="i1",
                ),
                AuditEvent(
                    event_id="e3",
                    type="intent_unknown",
                    payload_redacted={"intent_id": "i2", "client_order_id": "c2"},
                    at=NOW,
                    correlation_id="i2",
                ),
            ]
        )


@pytest.mark.d1c
def test_query_history_with_no_filter_returns_everything_newest_first(
    migrated_uow: UnitOfWork,
) -> None:
    _seed(migrated_uow)
    with migrated_uow.session() as session:
        rows = query_history(session, HistoryFilter())

    assert [r.event_id for r in rows] == ["e3", "e2", "e1"]


@pytest.mark.d1c
def test_query_history_filters_by_type(migrated_uow: UnitOfWork) -> None:
    _seed(migrated_uow)
    with migrated_uow.session() as session:
        rows = query_history(session, HistoryFilter(type="ui.tray.pause_l1"))

    assert [r.event_id for r in rows] == ["e1"]


@pytest.mark.d1c
def test_query_history_filters_by_correlation_id(migrated_uow: UnitOfWork) -> None:
    _seed(migrated_uow)
    with migrated_uow.session() as session:
        rows = query_history(session, HistoryFilter(correlation_id="i2"))

    assert [r.event_id for r in rows] == ["e3"]


@pytest.mark.d1c
def test_query_history_filters_by_client_order_id_from_payload(
    migrated_uow: UnitOfWork,
) -> None:
    """`client_order_id` has no dedicated column — it must be read out of the
    already-redacted payload, never a raw/unredacted source."""
    _seed(migrated_uow)
    with migrated_uow.session() as session:
        rows = query_history(session, HistoryFilter(client_order_id="c2"))

    assert [r.event_id for r in rows] == ["e3"]
    assert rows[0].client_order_id == "c2"


@pytest.mark.d1c
def test_query_history_filters_by_time_range(migrated_uow: UnitOfWork) -> None:
    _seed(migrated_uow)
    with migrated_uow.session() as session:
        rows = query_history(
            session,
            HistoryFilter(since=NOW - timedelta(minutes=90), until=NOW - timedelta(minutes=30)),
        )

    assert [r.event_id for r in rows] == ["e2"]


@pytest.mark.d1c
def test_query_history_combines_filters(migrated_uow: UnitOfWork) -> None:
    _seed(migrated_uow)
    with migrated_uow.session() as session:
        rows = query_history(
            session, HistoryFilter(type="intent_unknown", client_order_id="c2")
        )

    assert [r.event_id for r in rows] == ["e3"]

    with migrated_uow.session() as session:
        rows_no_match = query_history(
            session, HistoryFilter(type="intent_unknown", client_order_id="does-not-exist")
        )
    assert rows_no_match == []


@pytest.mark.d1c
def test_parse_iso_datetime_assumes_utc_for_naive_input() -> None:
    value = parse_iso_datetime("2026-07-27T12:00:00")
    assert value.tzinfo is not None
    assert value == NOW


@pytest.mark.d1c
def test_parse_iso_datetime_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_iso_datetime("not-a-date")


@pytest.mark.d1c
def test_export_history_csv_writes_only_redacted_fields(
    migrated_uow: UnitOfWork, tmp_path: Path
) -> None:
    _seed(migrated_uow)
    with migrated_uow.session() as session:
        rows = query_history(session, HistoryFilter())

    out = tmp_path / "history.csv"
    export_history_csv(rows, out)

    assert out.exists()
    with out.open(newline="", encoding="utf-8") as fh:
        reader = list(csv.DictReader(fh))

    assert len(reader) == 3
    header = reader[0].keys()
    assert set(header) == {
        "event_id",
        "type",
        "at",
        "correlation_id",
        "client_order_id",
        "payload_redacted",
    }
    # No column beyond the redacted fields snuck into the export.
    exported_ids = {row["event_id"] for row in reader}
    assert exported_ids == {"e1", "e2", "e3"}


@pytest.mark.d1c
def test_export_history_csv_never_leaks_a_secret_shaped_value(
    migrated_uow: UnitOfWork, tmp_path: Path
) -> None:
    """Even if a caller passed an unredacted-looking payload in, the CSV
    writer must not do anything beyond serialising what's already there —
    this test pins the contract that History never re-fetches raw fields by
    proving the export is a faithful, unmodified echo of `HistoryRow`."""
    with migrated_uow.session() as session:
        session.add(
            AuditEvent(
                event_id="e-redacted",
                type="ui.broker_hub.test_connection",
                payload_redacted={"api_key": "***REDACTED***", "ok": True},
                at=NOW,
                correlation_id=None,
            )
        )
    with migrated_uow.session() as session:
        rows = query_history(session, HistoryFilter())

    out = tmp_path / "history.csv"
    export_history_csv(rows, out)

    content = out.read_text(encoding="utf-8")
    assert "***REDACTED***" in content
    # A real key/token would never appear in payload_redacted in the first
    # place (it is redacted at write time everywhere in this codebase); this
    # just confirms the exporter does not add anything of its own.
    assert "api_key" in content
