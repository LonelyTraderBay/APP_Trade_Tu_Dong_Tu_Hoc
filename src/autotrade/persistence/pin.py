"""PIN Argon2id verifier (schema usable in D1a; Settings UI in D1c)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher(time_cost=2, memory_cost=64 * 1024, parallelism=2)


@dataclass(frozen=True, slots=True)
class PinState:
    salt: str
    hash: str
    failed_count: int = 0
    lockout_until: datetime | None = None


@dataclass(frozen=True, slots=True)
class PinVerifyResult:
    ok: bool
    state: PinState


def hash_pin(pin: str, *, salt: str | None = None) -> PinState:
    if not pin or len(pin) < 4:
        raise ValueError("PIN too short")
    salt_value = salt or secrets.token_hex(16)
    digest = _ph.hash(f"{salt_value}:{pin}")
    return PinState(salt=salt_value, hash=digest)


def verify_pin(state: PinState, pin: str, *, now: datetime | None = None) -> PinVerifyResult:
    current = now or datetime.now(UTC)
    if state.lockout_until and current < state.lockout_until:
        return PinVerifyResult(ok=False, state=state)

    try:
        _ph.verify(state.hash, f"{state.salt}:{pin}")
    except VerifyMismatchError:
        failed = state.failed_count + 1
        lockout = current + timedelta(minutes=15) if failed >= 5 else state.lockout_until
        return PinVerifyResult(
            ok=False,
            state=PinState(
                salt=state.salt,
                hash=state.hash,
                failed_count=failed,
                lockout_until=lockout,
            ),
        )

    return PinVerifyResult(
        ok=True,
        state=PinState(
            salt=state.salt,
            hash=state.hash,
            failed_count=0,
            lockout_until=None,
        ),
    )
