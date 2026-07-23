# Kế hoạch việc làm ngay (song song D1b V8 soak)

**Ngày**: 2026-07-23  
**Ràng buộc**: Không kill soak `soak_cb50ba…`; không phá DB `%LOCALAPPDATA%\AutoTradeAI`; không backdate cert.valid.

## Mục tiêu phiên này

Hoàn thiện phần **docs/Spec Kit D1c + Evidence tinh chỉnh + stub UI an toàn** trên `main` qua PR Enterprise. **Không** claim D1b exit kiến trúc (còn V8).

## Thứ tự ưu tiên

| Pri | ID | Việc | Done when |
|---|---|---|---|
| P0 | PLAN + Clarify | Khóa 3 Q D1c theo v1.4 (Owner-default) | research.md updated |
| P1 | Data + contracts | `data-model.md` + `contracts/*` D1c | files exist, khớp mục 09 |
| P2 | Tasks | `tasks.md` + checklist | implement gate rõ; tasks unchecked |
| P3 | Matrix | ADR-D09 ccxt=`4.5.68`; G1.1 REAL partial | matrix rows updated |
| P4 | Stub UI | `app_ui/` + optional `[ui]` + marker `d1c` | import không kéo Qt vào core; stub tests |
| P5 | PR | Squash merge Enterprise | PR URL + main clean |

## Ngoài phạm vi phiên này

- Chờ đủ 72h → enable-demo / valid=true  
- `/speckit-implement` Broker Hub đầy đủ / PyInstaller E2E  
- Rotate API key (sau V8)  
- LIVE / AI / Backtest  

## Clarify khóa (P0) — mặc định v1.4

1. **PIN vs Pause**: Pause/Flatten/tray Pause **không** bị PIN lockout chặn; Settings đổi secret + resume/nới risk **cần PIN** (mục 09).  
2. **Telegram first-run**: **Không bắt buộc** wizard Telegram lúc first launch; cấu hình trong Settings (headless D1a vẫn dùng được).  
3. **Packaging**: **one-folder** PyInstaller (ops/backup dễ hơn one-file).
