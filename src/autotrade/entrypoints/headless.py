"""Headless trading entrypoint (D1a).

No localhost HTTP listener — in-process composition only (ADR-D13).
"""

from __future__ import annotations

import argparse
import asyncio
import sys


def main(argv: list[str] | None = None) -> int:
    """Run headless entry; optional --smoke-runtime exercises OMS queue stub."""
    parser = argparse.ArgumentParser(
        prog="autotrade-headless",
        description="AutoTrade AI headless entry (D1a Paper core)",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print package version and exit",
    )
    parser.add_argument(
        "--smoke-runtime",
        action="store_true",
        help="Start Runtime OMS command-owner queue, echo one command, exit",
    )
    args = parser.parse_args(argv)

    if args.version:
        from autotrade import __version__

        print(__version__)
        return 0

    if args.smoke_runtime:
        return asyncio.run(_smoke_runtime())

    print(
        "autotrade-headless: ready (no HTTP). Use --smoke-runtime to exercise queue.",
        file=sys.stderr,
    )
    return 0


async def _smoke_runtime() -> int:
    from autotrade.core.runtime import Runtime

    runtime = Runtime()

    async def echo(cmd: object) -> object:
        return {"echo": cmd}

    runtime.set_handler(echo)
    await runtime.start()
    try:
        result = await runtime.submit({"ping": True})
        print(result)
    finally:
        await runtime.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
