"""Telegram transport — real Bot API or injectable fake for tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from autotrade.persistence.secrets import SecretRef, load_secret


class TelegramSender(Protocol):
    def send_message(self, chat_id: str, text: str) -> dict[str, Any]: ...


@dataclass
class FakeTelegramSender:
    """Test double: records messages; can inject transient/permanent failures."""

    messages: list[dict[str, str]] = field(default_factory=list)
    fail_transient_times: int = 0
    fail_permanent: bool = False
    _transient_left: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self._transient_left = self.fail_transient_times

    def send_message(self, chat_id: str, text: str) -> dict[str, Any]:
        if self.fail_permanent:
            raise PermanentTelegramError("400 Bad Request")
        if self._transient_left > 0:
            self._transient_left -= 1
            raise TransientTelegramError("429 Too Many Requests")
        self.messages.append({"chat_id": chat_id, "text": text})
        return {"ok": True}


class TransientTelegramError(RuntimeError):
    pass


class PermanentTelegramError(RuntimeError):
    pass


@dataclass
class TelegramTransport:
    sender: TelegramSender
    chat_id: str
    token_ref: SecretRef | None = None

    def send(self, text: str) -> dict[str, Any]:
        return self.sender.send_message(self.chat_id, text)

    def send_test_message(self) -> dict[str, Any]:
        return self.send("AutoTrade AI: test message (PAPER)")

    def token_present(self) -> bool:
        if self.token_ref is None:
            return True  # fake path
        return load_secret(self.token_ref) is not None
