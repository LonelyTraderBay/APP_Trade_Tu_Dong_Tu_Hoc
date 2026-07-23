"""Asyncio composition root + OMS command-owner queue stub (ADR-D13)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

CommandHandler = Callable[[Any], Awaitable[Any]]


@dataclass
class Runtime:
    """Single-process runtime: one OMS command owner queue, no HTTP."""

    _queue: asyncio.Queue[tuple[Any, asyncio.Future[Any]]] = field(
        default_factory=asyncio.Queue
    )
    _handler: CommandHandler | None = None
    _worker: asyncio.Task[None] | None = None

    def set_handler(self, handler: CommandHandler) -> None:
        self._handler = handler

    async def start(self) -> None:
        if self._worker is not None:
            return
        self._worker = asyncio.create_task(self._run_owner(), name="oms-command-owner")

    async def stop(self) -> None:
        if self._worker is None:
            return
        self._worker.cancel()
        try:
            await self._worker
        except asyncio.CancelledError:
            pass
        self._worker = None

    async def submit(self, command: Any) -> Any:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        await self._queue.put((command, fut))
        return await fut

    async def _run_owner(self) -> None:
        while True:
            command, fut = await self._queue.get()
            try:
                if self._handler is None:
                    raise RuntimeError("OMS command handler not configured")
                result = await self._handler(command)
                if not fut.done():
                    fut.set_result(result)
            except Exception as exc:  # noqa: BLE001 — surface to caller future
                if not fut.done():
                    fut.set_exception(exc)
            finally:
                self._queue.task_done()
