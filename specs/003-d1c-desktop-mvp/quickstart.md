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
