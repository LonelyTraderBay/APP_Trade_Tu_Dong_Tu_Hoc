# AGENTS.md — AutoTrade AI Desktop Solo

Hướng dẫn bắt buộc cho agent/developer khi làm việc trong repo này.

## Nguồn sự thật

1. **`Kien-truc-App-Desktop-Solo-v1.4.md`** — quy phạm kiến trúc (ưu tiên tuyệt đối).
2. **`.specify/memory/constitution.md`** — nguyên tắc dự án.
3. **`docs/mvp-capability-matrix.md`** — map yêu cầu → phase → test → evidence.

Enterprise blueprint (nếu có) chỉ tham khảo; **không** ghi đè v1.4.

## Phạm vi code theo phase

| Phase | Được làm | Cấm |
|---|---|---|
| **D0** | Chỉ tài liệu / gate Owner | Không scaffold trading app “cho vui” |
| **D1a** | Domain, SQLite ADR-D03.1, Paper, Risk, OMS, Recovery, Telegram | CCXT thật, UI đầy đủ, ML, `ai_*`, backtest UI |
| **D1b** | Một CCXT DEMO allowlist — tuple mục 16: `binance` + spot + Binance Spot Testnet + `BTC/USDT` + `15m` (D0-11 **xong**) | Multi-exchange, LIVE; không bỏ qua DEMO/certification để “cắm LIVE ngay” |
| **D1c** | PySide6 MVP + installer — Spec Kit `specs/003-d1c-desktop-mvp/` | AI Center, Backtest UI |
| **D3** | Backtest/replay deterministic | Train ML |
| **D4** | AI Module + Learning Store + sidecar | Auto-promote LIVE; AI gọi OMS |

**Backtest (D3) trước AI (D4).** Không cài scikit-learn / sqlite-vec / FAISS trong D1.

## Bất biến kỹ thuật (không thương lượng)

- Một process trading; không localhost HTTP API ở MVP.
- Mọi tăng exposure: Risk reservation + durable intent **commit trước** network.
- `UNKNOWN` / timeout sau send → query/recon; **không** retry mù.
- Broker = sự thật exposure hiện tại; SQLite = intent/FSM/audit/outbox.
- Secret chỉ `keyring`; redaction trong log/UI/DB.
- Strategy D1 mặc định: `rule_sma_cross_v1` (mục 07.3) trừ khi mục 16 ghi rule khác.
- Feature có `feature_schema_version`; chỉ closed candle.
- LIVE hard-disable tới gate D1.1 riêng; attended-only ở baseline.
- Exchange/symbol D1b **đã chốt** mục 16 (`binance` / spot / Binance Spot Testnet / `BTC/USDT` / `15m`). D1a dùng Paper + symbol nội bộ. Không implement CCXT trading trước khi D1a merge `main` + Spec Kit D1b plan/tasks.

## Cách triển khai an toàn

1. Đọc mục phase tương ứng trong v1.4 + hàng capability matrix trước khi sửa code.
2. Test trước: unit/FSM → contract adapter → fault matrix mục 18.
3. Không mở rộng scope “tiện thể” (MT5, multi-account, AI) vào PR D1.
4. Đổi ADR/semantics → cập nhật v1.4 + matrix + migration; không sửa âm thầm.
5. Không commit secret, PIN, token, Chat ID thật.

## Lệnh / layout mong đợi (khi đã có code)

- Package: `src/autotrade/` theo mục 13 v1.4.
- Tests: `tests/unit|contract|integration|fault|packaged`.
- Dev data: `data/` gitignore; runtime: `%LOCALAPPDATA%/AutoTradeAI/`.

## Khi mơ hồ

Dừng và hỏi Owner / cập nhật tài liệu. **Không** suy diễn từ Enterprise hay “best practice” chung để phá fail-closed, PIN, hoặc thứ tự D3→D4.
