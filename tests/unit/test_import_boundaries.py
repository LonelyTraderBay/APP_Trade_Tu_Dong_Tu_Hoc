"""Import boundary: strategy/risk/oms must not pull venue SDKs."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

FORBIDDEN = {"ccxt", "MetaTrader5", "metatrader5"}
PACKAGES = [
    Path("src/autotrade/core/strategy"),
    Path("src/autotrade/core/risk"),
    Path("src/autotrade/core/oms"),
]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


@pytest.mark.d1a
def test_no_venue_sdk_imports() -> None:
    offenders: list[str] = []
    for package in PACKAGES:
        if not package.exists():
            continue
        for py in package.rglob("*.py"):
            mods = _imports(py)
            bad = mods & FORBIDDEN
            if bad:
                offenders.append(f"{py}: {sorted(bad)}")
    assert offenders == []
