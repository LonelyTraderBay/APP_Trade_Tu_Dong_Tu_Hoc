# Feature Specification: D1c Desktop MVP (PySide6 + Installer)

**Feature Branch**: `003-d1c-desktop-mvp`  
**Created**: 2026-07-23  
**Status**: Draft — docs-first while D1b V8 soak runs; **implement gate** = D1b `certification_records.valid=true` (+ Evidence matrix)  
**Input**: Desktop Solo v1.4 mục 09/10/14 — UI tối thiểu + PyInstaller + ops Windows; không AI/Backtest UI/LIVE.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Install & first launch (Priority: P1)

Owner cài bản packaged trên Windows 11 x64 sạch, mở app một instance, thấy Dashboard + mode PAPER hoặc DEMO đã certify.

**Why this priority**: Không có installer/UI thì D1c không exit được.

**Independent Test**: Clean-machine install → launch → single-instance lock → quit.

**Acceptance Scenarios**:

1. **Given** máy Win11 sạch, **When** chạy installer, **Then** app cài vào đường dẫn chuẩn và tạo data dưới `%LOCALAPPDATA%/AutoTradeAI/`.
2. **Given** app đang chạy, **When** mở instance thứ hai, **Then** bị từ chối (single-instance).
3. **Given** app launched, **When** xem Dashboard, **Then** hiện equity/P&L/KS/health của account active; không lộ secret.

---

### User Story 2 — Broker Hub Paper ↔ DEMO (Priority: P1)

Owner Test Connection DEMO (đã valid cert), Switch account khi flat; UI không bypass Risk/OMS.

**Why this priority**: Đây là bề mặt vận hành chính sau D1b.

**Independent Test**: UI gọi cùng đường core như headless; enable-demo refused nếu cert invalid.

**Acceptance Scenarios**:

1. **Given** cert invalid, **When** Enable DEMO từ UI, **Then** refuse + thông báo rõ.
2. **Given** cert valid + flat, **When** switch Paper↔DEMO, **Then** mode tag khớp; non-flat/open recon/UNKNOWN → refuse.
3. **Given** DEMO connected, **When** Test Connection, **Then** capability redacted hiện trên UI.

---

### User Story 3 — Kill-switch & Live Monitor (Priority: P2)

Owner Pause (L1) từ UI/tray bất kể PIN lockout; thấy order/delivery kể cả UNKNOWN.

**Acceptance Scenarios**:

1. **Given** trading READY, **When** Pause, **Then** KS L1; không tăng exposure.
2. **Given** intent UNKNOWN, **When** mở Live Monitor, **Then** state UNKNOWN hiện; không nút “retry mù”.

---

### User Story 4 — Strategy / History / Settings / Tray (Priority: P3)

Strategy chỉ `rule_sma_cross_v1` (+ hard risk ceiling không UI override); History CSV; Settings PIN/Telegram/allowlist; Tray Pause/Open/Quit.

**Acceptance Scenarios**:

1. **Given** Settings, **When** lưu Telegram, **Then** token chỉ keyring; UI redacted.
2. **Given** tray, **When** Pause, **Then** cùng semantics core KS.

## Requirements *(mandatory)*

### Functional

- **FR-001**: UI chỉ PySide6 trong `app_ui/`; không localhost HTTP API (ADR-D13).
- **FR-002**: Mọi lệnh tăng exposure đi qua Risk reservation + durable intent (không bypass).
- **FR-003**: LIVE hard-disable trong D1c (giống D1b).
- **FR-004**: Single-instance + sleep/resume recovery checklist.
- **FR-005**: Backup/restore/manual upgrade paths theo v1.4 D1c exit.
- **FR-006**: Packaged E2E: clean install Win11 x64.
- **FR-007**: Operational soak tổng ≥14 ngày (sau MVP UI) — tách gate khỏi D1b 72h.

### Non-Functional

- Không thêm scikit-learn / sqlite-vec / FAISS / AI Center / Backtest UI.
- Secret chỉ keyring; redaction log/UI/DB.

## Success Criteria

- **SC-001**: Clean install + single-instance PASS.
- **SC-002**: Broker Hub Paper/DEMO switch fail-closed khớp headless.
- **SC-003**: Packaged sleep/resume + backup/restore PASS.
- **SC-004**: Không port listen ngoài process app.
- **SC-005**: `pytest -m "d1a or d1b"` vẫn xanh sau thêm UI deps (UI tests marker `d1c`).

## Out of Scope

- LIVE enablement (D1.1), multi-exchange, MT5, AI Center, Backtest UI, train ML.

## Assumptions

- D1b REAL V7 đã ≥50; V8 soak sẽ hoàn tất trước `/speckit-implement` runtime UI (hoặc Owner chấp nhận risk docs-only song song).
- Tuple DEMO không đổi trong D1c.
