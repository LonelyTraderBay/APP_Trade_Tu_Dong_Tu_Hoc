"""Headless trading entrypoint (D1a).

No localhost HTTP listener — in-process composition only (ADR-D13).
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    """Run headless stub. Full runtime composition lands in later D1a tasks."""
    parser = argparse.ArgumentParser(
        prog="autotrade-headless",
        description="AutoTrade AI headless entry (D1a Paper core stub)",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print package version and exit",
    )
    args = parser.parse_args(argv)

    if args.version:
        from autotrade import __version__

        print(__version__)
        return 0

    print(
        "autotrade-headless: stub ready (no HTTP). "
        "Wire composition root in later D1a tasks.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
