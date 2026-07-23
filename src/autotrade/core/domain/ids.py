"""Deterministic ID factories for intents, risk checks, correlations."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IdFactory:
    """Creates opaque identifiers without leaking secrets."""

    prefix: str = ""

    def uuid4(self) -> str:
        value = str(uuid.uuid4())
        return f"{self.prefix}{value}" if self.prefix else value

    def client_order_id(self) -> str:
        # Deterministic-length token suitable for broker client IDs.
        token = secrets.token_hex(16)
        return f"{self.prefix}c_{token}" if self.prefix else f"c_{token}"
