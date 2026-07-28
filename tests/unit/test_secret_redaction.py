"""Secret redaction scan."""

from __future__ import annotations

import pytest

from autotrade.core.domain.redaction import redact_mapping
from autotrade.core.notify.compose import compose_message


@pytest.mark.d1a
def test_secret_redaction_in_notify_payloads() -> None:
    text = compose_message(
        body="hello",
        account_id="paper1",
        extra={"bot_token": "123:ABC", "pin": "9999"},
    )
    assert "123:ABC" not in text
    assert "9999" not in text
    assert "***REDACTED***" in text
    assert redact_mapping({"api_key": "x"})["api_key"] == "***REDACTED***"
