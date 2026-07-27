# Quickstart: D1c Desktop MVP (docs phase)

**Gate**: D1b certification `valid=true` trước E2E UI DEMO.

## Now (docs only)

```text
# Đọc
specs/003-d1c-desktop-mvp/spec.md
specs/003-d1c-desktop-mvp/plan.md
```

## Now (Phase 2 — shell điều hướng, T010–T014 xong)

```text
# Không có Qt: entrypoint vẫn chạy và chỉ đường
autotrade-desktop
# → exit 2 + hướng dẫn pip install -e ".[ui]"

# Có Qt
pip install -e ".[ui]"        # hoặc: uv pip install "PySide6>=6.7,<7"
autotrade-desktop --check     # smoke headless: in banner mode/account/endpoint, exit 0
autotrade-desktop             # mở shell rỗng + tray (Pause không cần PIN)
```

**Exit code**: `0` bình thường · `2` thiếu extra `[ui]` · `3` đã có instance khác
(khoá mutex `AutoTradeAI.Solo`).

## Test

```text
pytest -m "d1a or d1b"                    # regression core
pytest -m d1c                             # UI/packaged
QT_QPA_PLATFORM=offscreen pytest -m d1c   # chạy cả test Qt trên máy không màn hình
```

Không cài `[ui]` thì 3 test Qt trong `tests/unit/test_ui_shell.py` tự skip; phần
logic (`app_ui/services`, `app_ui/controllers`) luôn chạy vì không phụ thuộc Qt.

## Later (sau D1b exit)

Broker Hub / Enable DEMO từ UI / packaged smoke — T020+ trong `tasks.md`, chờ
`certification_records.valid=true`.

## Out of scope here

LIVE, AI Center, Backtest UI, multi-exchange.

## Clean-machine install checklist

T020–T022. Verify a one-folder PyInstaller build on a machine that never had
this repo's `.venv` on it.

**Prerequisites**

- Windows 11 x64.
- No Python, no PySide6 needed — both are bundled in the one-folder output.
- Nothing listens on a TCP port (ADR-D13); no firewall prompt expected.

**Build** (on a dev machine with `.venv` + `packaging` extra)

```text
uv pip install --python .venv/Scripts/python.exe "pyinstaller>=6,<7"
# hoặc: pip install -e ".[packaging]"
.venv\Scripts\python.exe packaging\build.py          # → dist/AutoTradeAI/
.venv\Scripts\python.exe packaging\build.py --out D:\ci\out   # tuỳ chỉnh output dir
```

Copy the whole `dist/AutoTradeAI/` folder to the clean machine (zip it, or
robocopy) — everything it needs lives inside that folder.

**First launch (clean machine)**

```text
AutoTradeAI\AutoTradeAI.exe --check   # smoke: prints banner, exit 0, no window
AutoTradeAI\AutoTradeAI.exe           # opens empty MainWindow shell + tray (Phase 2 scope)
```

Expect on first real launch:

- `%LOCALAPPDATA%\AutoTradeAI\` is created fresh (SQLite DB + WAL/SHM under
  it — see `contracts/packaged-ops.md`).
- Single-instance guard acquires the `AutoTradeAI.Solo` named mutex before
  any window is built.
- Empty nav shell (Dashboard/Broker Hub/Kill-Switch/… placeholders) + tray
  icon; Pause in the tray works without a PIN.

**Verify single-instance**

```text
AutoTradeAI\AutoTradeAI.exe            # instance #1 — leave it running
AutoTradeAI\AutoTradeAI.exe --check    # instance #2, from a second terminal
# → exit 3, stderr: "autotrade-desktop is already running ..."
```

Automated version of the same check: `tests/packaged/test_packaged_launch.py`
(marker `d1c`; skips itself with a clear reason when
`dist/AutoTradeAI/AutoTradeAI.exe` isn't present).

**Uninstall / reinstall**

Deleting the `dist/AutoTradeAI/` (or installed) folder removes the app only
— it never touches `%LOCALAPPDATA%\AutoTradeAI\`. Before wiping that data
dir, back it up per `contracts/packaged-ops.md`:

- Backup = SQLite (+ WAL/SHM if present) + non-secret `ui_settings` only.
- Restore refuses on an incompatible `schema_meta`.
- Secrets are never restored in plaintext — re-enter them via the OS
  keyring after reinstall.
