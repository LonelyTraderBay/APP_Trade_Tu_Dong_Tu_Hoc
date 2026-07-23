# Research: D1c Desktop MVP

**Date**: 2026-07-23

## Decision: Docs-first during D1b V8 soak

- **Decision**: Viết spec/plan D1c ngay; trì hoãn `/speckit-implement` UI trading E2E tới khi D1b `valid=true`.
- **Rationale**: Soak 72h wall-clock đang chạy; tránh dual-write risk trên cùng máy Owner.
- **Alternatives**: Implement UI skeleton ngay (chấp nhận được nếu chỉ `app_ui` stub + không đụng cert DB).

## Decision: PySide6 optional extra

- **Decision**: `pyproject` extra `ui = ["PySide6…"]` — core `pip install` không kéo Qt.
- **Rationale**: Headless/CI D1a/D1b không cần GUI.
- **Alternatives**: Hard dep PySide6 (rejected — nặng CI).

## Decision: No HTTP local API

- **Decision**: UI in-process chỉ gọi UnitOfWork / Runtime queue (ADR-D13).
- **Rationale**: v1.4 bất biến.
- **Alternatives**: FastAPI localhost (rejected).

## Open questions (clarify trước tasks)

1. PIN unlock UX cho Settings vs Pause luôn available từ tray?
2. Có bắt buộc Telegram config trong first-run wizard D1c không?
3. PyInstaller one-file vs one-folder (v1.4 nghiêng one-folder ops)?

## Clarify locked 2026-07-23 (Owner-default = v1.4)

| Q | Decision | Source |
|---|---|---|
| PIN vs Pause | Pause / Flatten / tray Pause **không** bị PIN lockout; Settings (secret) + resume/nới risk **cần PIN** | v1.4 §09 KS + PIN |
| Telegram first-run | **Không bắt buộc** Telegram khi first launch; cấu hình trong Settings | D1a headless đã đủ; UX tối giản |
| Packaging | PyInstaller **one-folder** Windows x64 | v1.4 D1c ops / backup-restore |

Tasks và implement UI trading E2E vẫn **chờ** D1b `certification_records.valid=true` (sau V8 soak).
