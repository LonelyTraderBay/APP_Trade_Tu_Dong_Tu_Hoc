"""UI must not leak into core trading packages."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "src" / "autotrade"


def _is_pyside(name: str | None) -> bool:
    return bool(name) and (name == "PySide6" or name.startswith("PySide6."))


def _pyside_imports(path: Path) -> tuple[bool, bool]:
    """Return (imports_at_module_level, imports_anywhere).

    The distinction matters: a *lazy* import inside a function keeps the
    module importable without the [ui] extra, which is exactly how the
    desktop entrypoint is allowed to reach Qt.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module_level = False
    anywhere = False

    def visit(node: ast.AST, *, lazy: bool) -> None:
        nonlocal module_level, anywhere
        for child in ast.iter_child_nodes(node):
            hit = False
            if isinstance(child, ast.Import):
                hit = any(_is_pyside(a.name) for a in child.names)
            elif isinstance(child, ast.ImportFrom):
                hit = _is_pyside(child.module)
            if hit:
                anywhere = True
                if not lazy:
                    module_level = True
            deeper = lazy or isinstance(
                child, ast.FunctionDef | ast.AsyncFunctionDef
            )
            visit(child, lazy=deeper)

    visit(tree, lazy=False)
    return module_level, anywhere


def _imports_pyside(path: Path) -> bool:
    return _pyside_imports(path)[1]


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
def test_ui_logic_layer_stays_qt_free() -> None:
    """`app_ui/services` + `app_ui/controllers` must import without PySide6.

    They hold the read models and commands, so CI (which has no Qt) can test
    them. Only `app_ui/views` may reach for PySide6.
    """
    offenders: list[str] = []
    for sub in ("app_ui/services", "app_ui/controllers"):
        for path in (ROOT / sub).rglob("*.py"):
            if _imports_pyside(path):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


@pytest.mark.d1c
def test_ui_logic_layer_is_importable_without_the_extra() -> None:
    import importlib

    for module in (
        "autotrade.app_ui.services.dashboard",
        "autotrade.app_ui.services.screens",
        "autotrade.app_ui.services.single_instance",
        "autotrade.app_ui.controllers.tray",
    ):
        assert importlib.import_module(module) is not None


@pytest.mark.d1c
def test_only_the_view_layer_imports_qt_eagerly() -> None:
    """Whole-tree sweep: who is allowed to touch PySide6, and how.

    * `app_ui/views/**` — module-level import is fine, it is the Qt layer.
    * `entrypoints/desktop.py` — may import Qt, but only lazily inside a
      function, so `import autotrade.entrypoints.desktop` still works without
      the extra and can print the install hint.
    * everything else — must not reference PySide6 at all.
    """
    eager: list[str] = []
    lazy_only: list[str] = []
    for path in ROOT.rglob("*.py"):
        module_level, anywhere = _pyside_imports(path)
        if not anywhere:
            continue
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        (eager if module_level else lazy_only).append(rel)

    assert eager, "expected the view layer to import PySide6"
    assert all(p.startswith("app_ui/views/") for p in eager), eager
    assert lazy_only == ["entrypoints/desktop.py"], lazy_only


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
