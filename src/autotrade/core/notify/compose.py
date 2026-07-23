"""Outbound message composer — mode + account tags + redaction."""

from __future__ import annotations

from typing import Any

from autotrade.core.domain.redaction import redact_mapping, redact_text


def compose_message(
    *,
    body: str,
    mode: str = "PAPER",
    account_id: str,
    extra: dict[str, Any] | None = None,
) -> str:
    safe_extra = redact_mapping(extra or {})
    lines = [
        f"[{mode}] account={account_id}",
        redact_text(body),
    ]
    if safe_extra:
        lines.append(str(safe_extra))
    return "\n".join(lines)
