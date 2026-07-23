"""Keyring secret-ref helpers — never store plaintext secrets in SQLite."""

from __future__ import annotations

from dataclasses import dataclass

import keyring


@dataclass(frozen=True, slots=True)
class SecretRef:
    service: str
    username: str


def store_secret(ref: SecretRef, secret: str) -> None:
    if not secret:
        raise ValueError("secret must be non-empty")
    keyring.set_password(ref.service, ref.username, secret)


def load_secret(ref: SecretRef) -> str | None:
    return keyring.get_password(ref.service, ref.username)


def delete_secret(ref: SecretRef) -> None:
    try:
        keyring.delete_password(ref.service, ref.username)
    except keyring.errors.PasswordDeleteError:
        return
