"""Desktop entrypoint (D1c) — optional PySide6.

Does not start a localhost HTTP API (ADR-D13). Stub until MainWindow lands.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        import PySide6  # noqa: F401
    except ImportError:
        print(
            "autotrade-desktop requires optional extra [ui].\n"
            "  pip install -e \".[ui]\"\n"
            "Trading core remains available via autotrade-headless.",
            file=sys.stderr,
        )
        return 2

    # Full MainWindow is tasks T010+; stub proves entry + import gate only.
    print(
        "autotrade-desktop: PySide6 available — MainWindow not implemented yet "
        "(see specs/003-d1c-desktop-mvp/tasks.md T010). "
        "D1b soak/headless unaffected."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
