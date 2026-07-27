"""Thin wrapper around PyInstaller for the AutoTradeAI one-folder build (T020).

Builds `packaging/autotrade-desktop.spec` into `<out>/dist` and
`<out>/build`. Defaults to the repo-root `dist/` and `build/` dirs (both
already `.gitignore`d) — nothing here hardcodes an absolute machine path;
pass `--out` to redirect both elsewhere (e.g. a CI workspace).

Requires the `packaging` extra:
    .venv\\Scripts\\python.exe -m pip install -e ".[packaging]"
    # or: uv pip install --python .venv/Scripts/python.exe "pyinstaller>=6,<7"

Usage:
    .venv\\Scripts\\python.exe packaging\\build.py
    .venv\\Scripts\\python.exe packaging\\build.py --out C:\\ci\\workspace --clean
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "packaging" / "autotrade-desktop.spec"
APP_NAME = "AutoTradeAI"


def build(out_dir: Path, *, noconfirm: bool = True, clean: bool = False) -> int:
    """Run PyInstaller against the spec. Returns a process-style exit code."""
    try:
        import PyInstaller.__main__
    except ImportError:
        print(
            "PyInstaller is not installed in this environment. Install the\n"
            'optional "packaging" extra first:\n'
            '  .venv\\Scripts\\python.exe -m pip install -e ".[packaging]"\n'
            '  (or: uv pip install --python .venv/Scripts/python.exe "pyinstaller>=6,<7")',
            file=sys.stderr,
        )
        return 1

    dist_dir = out_dir / "dist"
    work_dir = out_dir / "build"

    pyi_args = [
        str(SPEC_PATH),
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
    ]
    if noconfirm:
        pyi_args.append("--noconfirm")
    if clean:
        pyi_args.append("--clean")

    print(f"[build] pyinstaller {' '.join(pyi_args)}")
    try:
        PyInstaller.__main__.run(pyi_args)
    except SystemExit as exc:
        code = exc.code
        if code not in (0, None):
            print(f"[build] FAILED — PyInstaller exited with: {code!r}", file=sys.stderr)
            return 1
    except Exception as exc:  # noqa: BLE001 - report, don't traceback the wrapper
        print(f"[build] FAILED — {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    exe_path = dist_dir / APP_NAME / f"{APP_NAME}.exe"
    if not exe_path.exists():
        print(f"[build] FAILED — expected exe missing: {exe_path}", file=sys.stderr)
        return 1

    print(f"[build] OK — {exe_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT,
        help="Base directory for dist/ and build/ output (default: repo root)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Pass --clean to PyInstaller (wipe its build cache first)",
    )
    args = parser.parse_args(argv)
    return build(args.out.resolve(), clean=args.clean)


if __name__ == "__main__":
    raise SystemExit(main())
