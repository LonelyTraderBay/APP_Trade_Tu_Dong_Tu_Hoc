"""Digest fields + mode tags."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from autotrade.core.notify.digest import DigestInput, build_digest


@pytest.mark.d1a
def test_digest_payload_fields() -> None:
    out = build_digest(
        DigestInput(
            account_id="paper1",
            mode="PAPER",
            pnl="12.5",
            order_count=3,
            drawdown="1.2",
            ks_level=1,
            adapter_health="ok",
            as_of=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
        )
    )
    assert out["mode"] == "PAPER"
    assert out["account"] == "paper1"
    assert out["fields"]["order_count"] == 3
    assert "[PAPER]" in out["text"]
    assert "as_of=" in out["text"]
