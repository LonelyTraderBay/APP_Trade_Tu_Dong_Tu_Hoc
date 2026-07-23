"""UI must not leak into core trading packages."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "src" / "autotrade"


def _imports_pyside(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "PySide6" or alias.name.startswith("PySide6."):
                    return True
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "PySide6" or node.module.startswith("PySide6."):
                return True
    return False


@pytest.mark.d1c
def test_core_packages_do_not_import_pyside6() -> None:
    offenders: list[str] = []
    for sub in ("core", "persistence"):
        base = ROOT / sub
        for path in base.rglob("*.py"):
            if _imports_pyside(path):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


@pytest.mark.d1c
def test_desktop_entrypoint_mentions_optional_ui() -> None:
    text = (ROOT / "entrypoints" / "desktop.py").read_text(encoding="utf-8")
    assert "[ui]" in text
    assert "PySide6" in text


@pytest.mark.d1c
def test_desktop_stub_exits_without_ui_extra() -> None:
    from autotrade.entrypoints.desktop import main

    try:
        import PySide6  # noqa: F401

        pytest.skip("PySide6 installed — skip missing-extra path")
    except ImportError:
        assert main([]) == 2
