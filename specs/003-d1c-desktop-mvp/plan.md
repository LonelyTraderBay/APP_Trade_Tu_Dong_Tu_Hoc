# Implementation Plan: D1c Desktop MVP

**Branch**: `003-d1c-desktop-mvp`  
**Date**: 2026-07-23  
**Spec**: [spec.md](./spec.md)  
**SoT**: `Kien-truc-App-Desktop-Solo-v1.4.md` mục 09, 10, 13, 14

## Summary

Thêm lớp PySide6 `app_ui/` + đóng gói PyInstaller; UI chỉ compose core đã có (Paper/DEMO/OMS/Risk/Telegram). Không HTTP API; không AI/Backtest.

## Technical Context

- **Language**: CPython 3.14.x (pin hiện tại)
- **UI**: PySide6 (optional extra `ui` trong pyproject)
- **Packaging**: PyInstaller one-folder Windows x64
- **Storage**: cùng SQLite `%LOCALAPPDATA%/AutoTradeAI/`
- **Testing**: `pytest -m d1c` (UI/packaged); giữ `d1a`/`d1b` regression

## Constitution Check

- Architecture doc law: UI không ghi đè fail-closed / PIN / cert gates.
- Phase order: D1c sau D1b; Backtest D3 → AI D4.
- No localhost trading API.

## Project Structure (target)

```text
src/autotrade/app_ui/          # D1c only
  main_window.py
  views/  # dashboard, broker_hub, monitor, strategy, history, settings
  tray.py
tests/packaged/                # installer / single-instance
tests/ui/                      # optional Qt tests
```

## Implementation gates

1. D1b `valid=true` + matrix Evidence (sau V8) — **hard gate** trước trading-from-UI E2E.
2. Spec/plan/tasks có thể viết trong lúc soak (docs-only).
3. `/speckit-implement` UI: không mở LIVE; không cài ML deps.

## Complexity Tracking

| Decision | Rationale |
|---|---|
| Optional `[ui]` extra | Core headless/CI không bắt buộc Qt |
| Implement gate = D1b valid | Tránh DEMO UI trước certification |

## Risks

- Soak D1b đang chạy: không kill process; không phá runtime DB.
- PySide6 wheel trên 3.14 — xác nhận trong research trước pin.
