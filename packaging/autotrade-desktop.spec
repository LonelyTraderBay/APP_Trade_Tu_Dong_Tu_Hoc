"""PyInstaller spec (T020): one-folder build of AutoTrade AI desktop.

Contract: specs/003-d1c-desktop-mvp/contracts/packaged-ops.md
  - "one-folder PyInstaller" — COLLECT, not a single onefile EXE. Per
    WORKPLAN-NOW.md: "ops/backup dễ hơn one-file" (easier ops/backup than
    one-file).
  - No listening TCP port in the packaged process (ADR-D13) — nothing here
    changes that; the app itself never opens one (see entrypoints/desktop.py).

Entry point mirrors the `autotrade-desktop` console-script shim
(pyproject.toml `[project.scripts]`): `_launcher.py` imports
`autotrade.entrypoints.desktop` and calls `main()`. PySide6 itself stays a
*lazy* import inside desktop.py (so the unpackaged CLI still runs without the
`[ui]` extra) — PyInstaller's static analysis still follows that import
because it scans every `import` statement in the module regardless of
nesting, so no extra hidden-import shim is needed for it.

Build via `python packaging/build.py`, or directly:
    pyinstaller packaging/autotrade-desktop.spec --noconfirm
"""

from __future__ import annotations

from pathlib import Path

# `spec_file_dir`/`SPECPATH` are injected into this namespace by PyInstaller
# when it exec()s the spec file, but resolving from __file__ keeps this spec
# importable/inspectable on its own too.
try:
    _SPEC_DIR = Path(SPECPATH).resolve()  # noqa: F821 - PyInstaller-injected
except NameError:
    _SPEC_DIR = Path(__file__).resolve().parent

REPO_ROOT = _SPEC_DIR.parent
SRC_DIR = REPO_ROOT / "src"
LAUNCHER = _SPEC_DIR / "_launcher.py"

APP_NAME = "AutoTradeAI"

a = Analysis(  # noqa: F821 - PyInstaller injects Analysis/PYZ/EXE/COLLECT
    [str(LAUNCHER)],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

# console=True keeps a real, always-attached stdio pipe so `--check` smoke
# runs (see tests/packaged/) can reliably capture the banner + exit code from
# an automated caller. A future pass can switch to a windowed build once the
# CLI-smoke path has a non-stdout signal to check instead.
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)
