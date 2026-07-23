"""D1a phase boundary: no CCXT/UI/AI modules; LIVE hard-disabled concept."""

from __future__ import annotations

from pathlib import Path

import pytest

from autotrade.core.adapters.manifest import PAPER_MANIFEST


@pytest.mark.d1a
def test_phase_boundary_d1a() -> None:
    root = Path("src/autotrade")
    forbidden_dirs = ["app_ui", "ai", "backtest", "plugins", "api"]
    for name in forbidden_dirs:
        assert not (root / name).exists()
        assert not (root / "core" / name).exists()

    # No ccxt import outside certified DEMO adapter package (D1b)
    offenders = []
    for py in root.rglob("*.py"):
        if "adapters" in py.parts and "ccxt_demo" in py.parts:
            continue
        text = py.read_text(encoding="utf-8")
        if "import ccxt" in text or "from ccxt" in text:
            offenders.append(str(py))
    assert offenders == []

    assert "LIVE" not in PAPER_MANIFEST.modes
    assert PAPER_MANIFEST.modes == ("PAPER",)
