"""Redaction helpers — secrets must never appear in journal/logs/tests."""

from __future__ import annotations

import re
from typing import Any

_SECRET_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "bot_token",
        "pin",
        "authorization",
        "private_key",
    }
)

_REDACTED = "***REDACTED***"

# Long hex/base64-ish tokens that look like credentials in free text.
_TOKEN_RE = re.compile(r"(?i)(bearer\s+)[a-z0-9\-._~+/]+=*")


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in _SECRET_KEYS or any(s in key.lower() for s in _SECRET_KEYS):
            out[key] = _REDACTED
        elif isinstance(value, dict):
            out[key] = redact_mapping(value)
        elif isinstance(value, list):
            out[key] = [
                redact_mapping(v) if isinstance(v, dict) else redact_text(str(v))
                if isinstance(v, str)
                else v
                for v in value
            ]
        elif isinstance(value, str):
            out[key] = redact_text(value)
        else:
            out[key] = value
    return out


def redact_text(text: str) -> str:
    return _TOKEN_RE.sub(r"\1" + _REDACTED, text)
