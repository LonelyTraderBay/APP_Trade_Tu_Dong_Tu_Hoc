"""Frozen entry script for the packaged AutoTradeAI build (T020).

PyInstaller's Analysis needs a real script file to seed its import graph
from. This mirrors exactly what the `autotrade-desktop` console-script shim
(pyproject.toml `[project.scripts]`) does: import
`autotrade.entrypoints.desktop` and call `main()`, passing through
argv (e.g. `AutoTradeAI.exe --check`).
"""

from __future__ import annotations

from autotrade.entrypoints.desktop import main

if __name__ == "__main__":
    raise SystemExit(main())
