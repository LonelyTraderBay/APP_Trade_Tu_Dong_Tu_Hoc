# App Auto-Trade AI — Personal Desktop (Solo)

> Profile sản phẩm từ `Kien-truc-Bot-Auto-Trade-AI-v2-Enterprise.md` cho **một người, Windows desktop, không login**.
>
> **Nguồn sự thật phạm vi & mục tiêu:** file này. Enterprise chỉ là tham chiếu kỹ thuật sâu (FSM, risk số, AI loop).
>
> **Trạng thái:** v1.1 — thống nhất mục tiêu chi tiết **trước khi code**. Chưa triển khai mã nguồn.

| | |
|---|---|
| **PHIÊN BẢN** | v1.1 — mục tiêu thống nhất (đa sàn + demo + Telegram + ngôn ngữ chốt) |
| **ĐỐI TƯỢNG** | Chủ sở hữu vốn tự trade — hồ sơ pháp lý **(a)** |
| **NỀN TẢNG** | Windows 10/11 |
| **AUTH** | Không đăng nhập tài khoản app; chỉ PIN local cho hành động nguy hiểm |
| **NGÔN NGỮ** | **Python 3.11+** (một runtime chính — xem ADR-D01) |
| **KẾT NỐI** | Kiến trúc **adapter cắm được**: Owner tự thêm/cấu hình sàn trong app |
| **BÁO CÁO** | Telegram là kênh báo cáo chính (bắt buộc từ MVP) |
| **CHƯA CODE** | Chỉ cập nhật kiến trúc / mục tiêu cho tới khi Owner ra lệnh mở D1 |

### Lịch sử phiên bản (file này)

| Ver | Ngày | Thay đổi |
|---|---|---|
| v1.0 | 2026-07-23 | Profile desktop solo rút từ Enterprise |
| v1.1 | 2026-07-23 | Thống nhất: đa sàn (plugin), demo/live, Telegram bắt buộc, chốt Python-only; chi tiết mục tiêu trước code |

---

## 00. Tầm nhìn sản phẩm (một câu)

> Phần mềm desktop cá nhân giúp Owner **tự kết nối bất kỳ sàn/broker nào hệ thống hỗ trợ (demo hoặc thật)**, bot giao dịch có **risk + kill-switch**, AI tự học trên máy, và **báo cáo/cảnh báo qua Telegram** — không cần login, không SaaS, không phụ thuộc đội vận hành.

---

## 01. Mục tiêu thống nhất (chi tiết — Definition of Done sản phẩm)

Mỗi mục tiêu có tiêu chí “xong” đo được. Đây là hợp đồng phạm vi trước khi viết code.

### G1 — Đa sàn / tự kết nối (cốt lõi sản phẩm)

| # | Mục tiêu chi tiết | Tiêu chí xong |
|---|---|---|
| G1.1 | Lõi **không** hard-code một sàn. Mọi sàn đi qua **Broker Adapter Interface** thống nhất. | Thêm sàn mới = thêm 1 module adapter + đăng ký manifest; **không** sửa Strategy / Risk / OMS / AI |
| G1.2 | Owner **tự kết nối** trong app (wizard), không cần sửa code. | Form: chọn loại adapter → nhập credential → Test connection → lưu (secret vào keyring) → chọn Demo/Live |
| G1.3 | Hỗ trợ họ kết nối theo **nhóm adapter**, mở rộng dần theo roadmap (không hứa “mọi sàn thế giới ngày 1”). | Nhóm A/B/C ở mục 05; UI chỉ hiện adapter đã ship + trạng thái “sắp có” |
| G1.4 | Chuẩn hoá symbol / timeframe / order type về model nội bộ. | Bảng `symbol_map` per account; Strategy chỉ thấy symbol nội bộ |
| G1.5 | Nhiều tài khoản song song (ví dụ 1 MT5 demo + 1 Binance demo). | Mỗi account có `adapter_id`, `mode`, risk scope riêng; kill-switch theo account hoặc global |

**Ý nghĩa “bất kể sàn nào”:**  
Không phải viết sẵn 200 connector ngày đầu. Nghĩa là **hạ tầng sẵn sàng** để Owner gắn thêm sàn thuộc nhóm đã hỗ trợ (đặc biệt **mọi sàn CCXT** + **MT5** + adapter chứng khoán sau), và quy trình thêm adapter mới rõ ràng, không đụng lõi.

### G2 — Demo / Paper / Live

| # | Mục tiêu | Tiêu chí xong |
|---|---|---|
| G2.1 | Mỗi account gắn đúng một **Trading Mode**: `DEMO` \| `PAPER` \| `LIVE` | Mode hiện rõ trên Dashboard, tray, mọi lệnh Telegram |
| G2.2 | `DEMO` = tài khoản demo của sàn/broker (MT5 demo, Binance testnet/demo, v.v.) | Credential demo tách biệt live; không trộn key |
| G2.3 | `PAPER` = mô phỏng nội bộ (không gửi lệnh sàn) dùng data thật hoặc replay | Đủ để test strategy/AI khi chưa có demo sàn |
| G2.4 | `LIVE` khoá mặc định; chỉ mở sau PIN + gõ `LIVE` + checklist | Audit ghi thời điểm bật live |
| G2.5 | Mặc định xuất xưởng: chỉ cho phép tạo account `DEMO` hoặc `PAPER` | Live phải opt-in có chủ đích |

### G3 — An toàn vốn (không thương lượng)

| # | Mục tiêu | Tiêu chí xong |
|---|---|---|
| G3.1 | 100% lệnh ra sàn đi qua Risk (fail-closed) | Có bản ghi `risk_checks` cho mọi submit |
| G3.2 | Kill-switch L1–L4 hoạt động từ UI + tray + lệnh Telegram (xem G5) | Game-day trên DEMO: L3 flatten trong mục tiêu ≤30s (tài sản thanh khoản) |
| G3.3 | OMS: idempotency + trạng thái `UNKNOWN` → poll, không retry mù | Chaos test timeout ack trên DEMO |
| G3.4 | Recon: lệch ledger ↔ sàn → L2 + Telegram; sàn là sự thật | Ít nhất 1 drill trên DEMO |

### G4 — Giao dịch & AI

| # | Mục tiêu | Tiêu chí xong |
|---|---|---|
| G4.1 | MVP: 1 chiến lược rule-based trên 1 account DEMO | Chạy ổn định ≥14 ngày DEMO/PAPER |
| G4.2 | Sau MVP: AI sinh xác suất hiệu chỉnh + giải thích nhẹ | Shadow trên DEMO trước khi gắn LIVE |
| G4.3 | Tự huấn luyện lại trên máy (CPU), promote có xác nhận Owner | Rollback model tự động khi suy giảm |

### G5 — Báo cáo & điều khiển qua Telegram (bắt buộc)

| # | Mục tiêu | Tiêu chí xong |
|---|---|---|
| G5.1 | Owner cấu hình Bot Token + Chat ID trong Settings (secret qua keyring) | Nút “Gửi tin thử” thành công |
| G5.2 | Báo cáo đẩy (push) theo sự kiện — không chỉ log file | Đủ các loại ở bảng Telegram (mục 08) |
| G5.3 | Báo cáo định kỳ (digest): cuối ngày / tuần (cấu hình được) | P&L, số lệnh, drawdown, trạng thái kill-switch, health adapter |
| G5.4 | Điều khiển tối thiểu từ Telegram (tuỳ chọn bật): `/status` `/pause` `/resume_l1` — **không** flatten L3 từ chat trừ khi bật “Telegram dangerous commands” + PIN đã xác nhận trước trong app | Mặc định: chỉ `/status` và nhận báo cáo; lệnh nguy hiểm off |
| G5.5 | Mọi tin Telegram gắn `mode` (DEMO/PAPER/LIVE) và `account` | Tránh nhầm demo với live |

### G6 — Desktop một người, không login

| # | Mục tiêu | Tiêu chí xong |
|---|---|---|
| G6.1 | Mở app → Dashboard; không form đăng nhập cloud | — |
| G6.2 | PIN local cho: bật LIVE, đổi risk, L3/L4, xem/xoá secret, bật lệnh nguy hiểm Telegram | — |
| G6.3 | System tray: trạng thái, P&L ngày, Pause (L1), mở app | — |
| G6.4 | Single-instance lock | Không chạy 2 process trading |

### G7 — Trải nghiệm “tự kết nối” (UX)

Wizard **Kết nối sàn** (màn Broker Hub):

1. Chọn **nhóm**: Crypto (CCXT) / MetaTrader 5 / Chứng khoán (sau) / Paper nội bộ  
2. Chọn **sàn cụ thể** (ví dụ danh sách CCXT: Binance, Bybit, OKX, …)  
3. Chọn **mode**: DEMO / LIVE (LIVE bị khoá tới khi đủ điều kiện)  
4. Nhập credential theo template adapter (API key, secret, password, server MT5, …)  
5. **Test connection** → hiện số dư / tên account / quyền (trade? withdraw?)  
6. Cảnh báo nếu crypto key còn quyền rút tiền  
7. Lưu → hiện trong danh sách account → gán strategy  

Owner **không** cần biết code để thêm một sàn thuộc nhóm đã ship.

---

## 02. Ngoài phạm vi (cố ý)

- Login / JWT / RBAC / multi-tenant / SaaS / App Store cloud account  
- Dual-control 2 người, màn Approvals enterprise  
- Kafka, Kubernetes, Vault HA, multi-region DR, on-call SRE  
- “Kết nối mọi sàn trên trái đất” trong ngày đầu nếu chưa có adapter (chỉ hứa **nền tảng mở rộng**)  
- Quản lý vốn hộ người khác  
- Mobile app native  
- Tư vấn đầu tư tự động mang tính pháp lý tư vấn  

---

## 03. Quyết định ngôn ngữ & stack (chốt — nhẹ, ổn định)

### So sánh ngắn (để đóng tranh luận)

| Lựa chọn | Ưu | Nhược | Phù hợp? |
|---|---|---|---|
| **Python only** (core + UI Qt) | Một runtime; CCXT/MT5/ML sẵn; ổn định lâu dài; dễ bảo trì solo | UI không “web-fancy” bằng React | **Chọn** |
| Python + Tauri/React | UI đẹp, chart web | 2–3 toolchain (Python+Rust+Node); nặng vận hành solo | Không chọn giai đoạn này |
| Node/TS toàn bộ | UI mạnh | Yếu hệ sinh thái MT5 + ML train + nhiều broker chính thống | Không |
| C#/Rust core | Hiệu năng | Tốn thời gian; thiếu CCXT/MT5 ecosystem tương đương | Không |

### ADR-D01 — Ngôn ngữ chính: Python 3.11+ (một runtime)

**Quyết định:** Toàn bộ trading core **và** UI desktop dùng **Python 3.11+**.

| Thành phần | Thư viện |
|---|---|
| UI desktop | **PySide6 (Qt 6)** — nhẹ hơn Electron, ổn định trên Windows, tray/native dialog tốt |
| Chart | `pyqtgraph` hoặc WebEngine nhúng Lightweight Charts (chọn 1 ở D1; mặc định đề xuất **pyqtgraph** cho nhẹ) |
| Local API nội bộ (optional) | FastAPI/uvicorn chỉ `127.0.0.1` nếu cần tách process; MVP có thể gọi module trực tiếp trong cùng process |
| Async / I/O | `asyncio` + thread cho SDK blocking (MT5) |
| Crypto đa sàn | **CCXT** (và ccxt.pro/async nếu cần WS) |
| Forex/CFD | **MetaTrader5** (official, cùng máy) |
| DB | SQLite (WAL) + SQLAlchemy 2.x |
| ML | scikit-learn, XGBoost/LightGBM, Optuna |
| Secret | `keyring` (Windows Credential Manager) |
| Telegram | `python-telegram-bot` hoặc HTTP Bot API mỏng |
| Test / quality | pytest, ruff, mypy (gradually) |

**Lý do “nhẹ + ổn định”:** một ngôn ngữ, ít moving parts, đúng ecosystem broker/AI, Qt native không nuốt RAM như Electron.

**Không dùng ở baseline:** Electron, Kubernetes, Kafka.

### ADR-D02 — Không login app

Mở app = vào Dashboard. PIN local cho hành động nguy hiểm (mục G6.2).

### ADR-D03 — SQLite

DB local một file trong `%APPDATA%/AutoTradeAI/` (hoặc thư mục `data/` lúc dev). Backup = copy file DB + nhắc Owner.

### ADR-D04 — Bus nội bộ

Không Kafka. `asyncio.Queue` + bảng `events` append-only.

### ADR-D05 — MT5

Official `MetaTrader5` trên cùng Windows. Terminal phải chạy. Disconnect → L1 account MT5 + Telegram.

### ADR-D06 — Secret

Chỉ `keyring`. UI chỉ hiện masked. Không ghi plaintext vào SQLite/config.

### ADR-D07 — Reporting currency

Mặc định USD; tuỳ chọn hiển thị VND (FX lưu theo sự kiện).

### ADR-D08 — Đóng gói

PyInstaller / briefcase / tương đương → một bộ cài Windows. Dev chạy từ source.

### ADR-D09 — Adapter plugin là xương sống

Mọi kết nối sàn = implementation của interface (mục 05). CCXT = **một adapter generic** nhận `exchange_id` → phủ hàng trăm sàn crypto mà không viết từng file Binance/Bybit riêng (trừ khi cần custom).

### ADR-D10 — Telegram là kênh báo cáo hạng mục P0

Không hoãn sau MVP. Không có Telegram cấu hình xong thì chưa đạt exit D1.

---

## 04. Kiến trúc tổng thể

```
┌──────────────────────────────────────────────────────────┐
│  Desktop UI (PySide6)                                     │
│  Dashboard · Broker Hub (wizard) · Live · Strategy        │
│  Risk/Kill · AI · Backtest · History · Settings · Tray    │
└──────────────────────────┬───────────────────────────────┘
                           │ in-process calls (MVP)
                           │ (optional: HTTP 127.0.0.1)
┌──────────────────────────▼───────────────────────────────┐
│  Trading Core (Python modular monolith)                   │
│                                                           │
│  Broker Hub ──► Adapter Registry ──► Adapters[]           │
│       │              │                 │                  │
│       │              │    ┌────────────┼─────────────┐    │
│       │              │    │ CCXT       │ MT5 │ Paper │    │
│       │              │    │ (mọi exchange_id           │    │
│       │              │    │  được allowlist) │  │     │    │
│       ▼              ▼    └────────────┴─────┴─────┘    │
│  Market Data → Features → Strategy/AI                     │
│                         → Risk (sync, fail-closed)        │
│                         → OMS → Adapter.place/cancel      │
│                         → Ledger + Recon                  │
│  Notify Fan-out → Telegram + Windows Toast                │
│  SQLite + keyring                                         │
└──────────────────────────────────────────────────────────┘
```

**Đường găng:** Strategy → Risk → OMS → Adapter (đồng bộ, timeout = fail-closed).

---

## 05. Broker Adapter — hạ tầng “tự kết nối mọi sàn hỗ trợ”

### 05.1 Interface bắt buộc (mọi adapter)

```
connect() / disconnect() / health()
subscribe_market_data() | poll_ohlcv()
get_ohlcv(symbol, timeframe, since, limit)
place_order(intent) → broker_order_ref
cancel_order(client_order_id | broker_order_id)
get_order_status(...)
get_positions() / get_balance() / get_fees() / get_margin_state()
normalize_symbol() / list_tradable_symbols()
supports_demo() → bool
account_mode_detected() → DEMO | LIVE | UNKNOWN
```

Kèm: rate-limit budget, map lỗi → lỗi nội bộ, không ném raw exception lên UI.

### 05.2 Manifest adapter (đăng ký)

Mỗi adapter khai báo:

| Field | Ví dụ |
|---|---|
| `adapter_id` | `ccxt`, `mt5`, `paper`, `ibkr` (sau) |
| `display_name` | “Crypto (CCXT)” |
| `credential_schema` | JSON form fields (key, secret, password, server, …) |
| `modes_supported` | DEMO, LIVE |
| `markets` | crypto / forex / stocks |
| `capability` | spot, swap, stop_native, … |
| `setup_help` | text hướng dẫn Owner lấy key / mở demo |

UI Broker Hub đọc registry → render form động từ `credential_schema`.

### 05.3 Nhóm hỗ trợ (roadmap kết nối)

| Nhóm | Phạm vi | Cách Owner tự nối | Phase ship |
|---|---|---|---|
| **A — Paper** | Mô phỏng nội bộ | Một click “Tạo tài khoản Paper” | D1 (cùng lúc core) |
| **B — Crypto qua CCXT** | Các sàn CCXT hỗ trợ (Binance, Bybit, OKX, Bitget, …) | Chọn exchange_id → API key demo/testnet hoặc live | D1: 1–2 exchange allowlist; D1.1: mở allowlist rộng + testnet flags |
| **C — MetaTrader 5** | Forex/CFD/vàng qua terminal MT5 | Login + password + server; account demo broker | D1 hoặc D1.1 (Windows) |
| **D — Chứng khoán** | IBKR / Alpaca, … | Adapter riêng | D4+ |
| **E — Custom** | Sàn lạ không có trong CCXT | Owner (hoặc dev) viết plugin theo interface + thả vào thư mục `adapters/plugins/` | Sau khi ổn A–C |

**Allowlist D1 (an toàn):** cấu hình `enabled_exchanges: ["binance", "bybit", "okx"]` (ví dụ) — Owner có thể mở rộng list trong Settings khi chấp nhận rủi ro ToS/API.

**Không** hard-code logic Binance trong Strategy. Chỉ `adapter_id=ccxt` + `exchange_id=binance`.

### 05.4 Demo theo từng họ

| Họ | Cách DEMO |
|---|---|
| CCXT | Testnet/sandbox flag của sàn nếu có; hoặc account demo sàn cung cấp; nếu sàn không có demo → dùng Paper nội bộ + data live đọc-only |
| MT5 | Tài khoản demo từ broker (server demo) |
| Paper | Luôn demo/mô phỏng |

UI phải hiện rõ: “Đang nối DEMO” vs “LIVE” (màu / nhãn / Telegram prefix).

### 05.5 Quy trình thêm sàn mới (cho tương lai — chưa code)

1. Implement interface + manifest  
2. Contract test: mock place/cancel/status/partial/balance  
3. Đăng ký registry  
4. Manual: nối DEMO thật → 10 lệnh paper/demo  
5. Bật trong allowlist  

---

## 06. Chế độ tài khoản & an toàn LIVE

```
PAPER  → không gửi lệnh sàn
DEMO   → gửi lệnh tài khoản demo/testnet
LIVE   → tiền thật (PIN + xác nhận)
```

Chuyển DEMO→LIVE: không tái sử dụng nhầm credential; bắt buộc tạo/chọn account LIVE riêng.

Checklist bật LIVE (ghi trong UI):

- [ ] Đã chạy DEMO/PAPER ≥ số ngày Owner đặt (mặc định đề xuất 14)  
- [ ] Kill-switch đã thử trên DEMO  
- [ ] Telegram nhận được SEV1 test  
- [ ] Risk limit đã điền  
- [ ] API key không có quyền withdraw (crypto)  

---

## 07. Risk & Kill-switch

### Limit mặc định (Owner chỉnh)

| Limit | Mặc định |
|---|---|
| Rủi ro / lệnh | ≤ 1% vốn account |
| Exposure / symbol | ≤ 20% |
| Exposure / strategy | ≤ 30% |
| Gross exposure | ≤ 100% (không đòn bẩy) / ≤ 150% (có) |
| Margin usage | ≤ 70% |
| Lỗ ngày | −3% → L1; −5% → L3 |
| Lỗ 7 ngày | −8% → L2 (resume + PIN) |
| Thua liên tiếp | 6 → L1 strategy |
| Kelly | ≤ 25% full-Kelly |
| Ngoài session | Không entry mới |

### Kill-switch

| Mức | Hành động | Resume |
|---|---|---|
| L1 | Pause entry | Auto cooldown 15' (≤2 lần/24h) hoặc tay |
| L2 | Huỷ pending; chặn lệnh mới | Tay + PIN |
| L3 | Flatten | Tay + PIN + Confirm |
| L4 | Flatten + khoá trade trong app | Tay + PIN + gõ `UNLOCK` |

Telegram: luôn báo khi đổi mức; điều khiển L3 từ Telegram **mặc định tắt**.

---

## 08. Telegram — báo cáo chi tiết

### Cấu hình

- Bot Token + Chat ID (hoặc danh sách ID whitelist)  
- Secret trong keyring  
- Múi giờ báo cáo (mặc định giờ máy / giờ Việt Nam cấu hình được)  
- Ngôn ngữ tin nhắn: **Tiếng Việt** (mặc định)

### Sự kiện đẩy ngay

| Sự kiện | Mức | Nội dung tối thiểu |
|---|---|---|
| Bot start/stop | info | version, accounts connected |
| Kết nối adapter OK/FAIL | info/SEV2 | adapter, account, mode |
| Lệnh filled / rejected | info | symbol, side, qty, price, mode |
| Risk reject | info | lý do limit |
| Kill-switch đổi mức | SEV1/2 | level, scope, lý do |
| Recon break | SEV1 | lệch gì, giá trị |
| Feed stale / MT5 disconnect | SEV2 | symbol/account |
| Model rollback | SEV1 | version cũ ← mới |
| Bật LIVE | SEV1 | account id masked |

### Digest định kỳ

| Digest | Nội dung |
|---|---|
| Cuối ngày | P&L ngày, số lệnh thắng/thua, max DD ngày, trạng thái KS, health |
| Cuối tuần | P&L tuần, equity change, top symbol, cảnh báo mở |

### Lệnh Telegram (mặc định an toàn)

| Lệnh | Mặc định | Ghi chú |
|---|---|---|
| `/status` | Bật | equity, mode, KS, kết nối |
| `/pnl` | Bật | P&L ngày |
| `/pause` | Bật | = L1 global hoặc account chỉ định |
| `/resume_l1` | Bật | chỉ resume L1 |
| `/flatten` | **Tắt** | chỉ bật trong Settings nâng cao |

Mọi lệnh ghi `audit_events`.

---

## 09. UI desktop — màn hình

| Màn | Việc |
|---|---|
| **Dashboard** | Equity, P&L, bot, SEV, health từng account (DEMO/LIVE badge) |
| **Broker Hub** | Danh sách account + **Wizard kết nối** + Test + Disconnect |
| **Kill-switch** | L1–L4 luôn hiện |
| **Live Monitor** | Giá, tín hiệu, lệnh (kể cả UNKNOWN), stale |
| **Strategy** | Gán strategy ↔ account; tham số; risk ceiling |
| **AI Center** | Model versions, train, promote, rollback (sau D1) |
| **Backtest** | Job + kết quả |
| **History** | Lệnh, CSV, tra cứu id |
| **Settings** | PIN, Telegram, allowlist exchange, currency, autostart, data path, backup |
| **Tray** | Status, P&L, Pause, Open, Quit (cảnh báo nếu còn vị thế) |

---

## 10. Module backend & phase

| Module | D1 MVP | Ghi chú |
|---|---|---|
| Adapter Registry + Interface | P0 | Xương sống đa sàn |
| Paper adapter | P0 | |
| CCXT adapter + allowlist | P0 | Ít nhất 1 exchange DEMO chạy E2E |
| MT5 adapter | P0/P1 | Cùng D1 nếu Owner ưu tiên forex; không thì D1.1 |
| Market / Feature / Strategy rule | P0 | |
| Risk + Kill-switch | P0 | |
| OMS + Ledger + Recon | P0 | |
| Telegram notify + digest + `/status` `/pause` | P0 | |
| UI PySide6 đủ màn MVP | P0 | |
| Backtest cơ bản | P1 | |
| AI inference / train | D2 / D3 | |

---

## 11. Vòng đời lệnh (giữ tinh thần Enterprise)

```
CREATED → RISK_APPROVED | RISK_REJECTED
       → SUBMITTED → ACKNOWLEDGED | UNKNOWN
UNKNOWN → bắt buộc get_order_status trước mọi hành động
ACKNOWLEDGED → PARTIAL → FILLED | CANCELED | REJECTED | EXPIRED
```

---

## 12. AI (sau khi đa sàn + DEMO ổn)

Target: `P(lợi nhuận(H) > ngưỡng sau phí)` đã hiệu chỉnh.  
Shadow trên DEMO → Owner promote → rollback tự động.  
Không auto-promote 100% vốn LIVE.

---

## 13. Cấu trúc thư mục đề xuất (chưa tạo code)

```
APP_Trade_Tu_Dong_Tu_Hoc/
├── Kien-truc-Bot-Auto-Trade-AI-v2-Enterprise.md
├── Kien-truc-App-Desktop-Solo-v1.md          # file này
├── AGENTS.md                                 # tạo trước khi code
├── docs/
│   └── mvp-capability-matrix.md
├── src/
│   └── autotrade/                            # Python package
│       ├── app_ui/                           # PySide6
│       ├── core/
│       │   ├── adapters/                     # interface + ccxt + mt5 + paper
│       │   │   └── plugins/                  # adapter bổ sung sau
│       │   ├── market/
│       │   ├── features/
│       │   ├── strategy/
│       │   ├── risk/
│       │   ├── oms/
│       │   ├── ledger/
│       │   ├── ai/
│       │   ├── backtest/
│       │   ├── notify/                       # telegram + toast
│       │   └── api/                          # optional localhost
│       └── persistence/                      # sqlite models
├── tests/
└── data/                                     # gitignore
```

---

## 14. Lộ trình (mục tiêu trước code)

| Giai đoạn | Mục tiêu | Exit (đo được) |
|---|---|---|
| **D0 — Thống nhất** *(đang ở đây)* | Chốt mục tiêu G1–G7, ADR, Telegram P0, Python-only, đa sàn plugin | Owner **duyệt file v1.1**; còn lại chỉ số liệu cá nhân (mục 16) |
| **D1 — MVP nối sàn + an toàn** | UI + Registry + Paper + CCXT (allowlist) + Risk/OMS/KS + Telegram + DEMO E2E | ≥14 ngày DEMO/PAPER; Telegram digest OK; 0 lệnh trùng; L3 thử trên DEMO |
| **D1.1** | Mở rộng allowlist CCXT + MT5 (nếu chưa có) + wizard hoàn chỉnh | ≥2 họ adapter khác nhau trên DEMO |
| **D2** | AI inference + shadow DEMO | Shadow ổn; live nhỏ chỉ khi Owner muốn |
| **D3** | Retrain + registry + rollback | 1 chu kỳ đầy đủ |
| **D4+** | IBKR/Alpaca, plugin folder, backup wizard | Vẫn không multi-user |

**Nguyên tắc:** chưa xong D0 (duyệt mục tiêu) thì **không viết code** trading.

---

## 15. Backlog tài liệu / chuẩn bị (trước code)

| ID | Việc | Trạng thái |
|---|---|---|
| D0-01 | Duyệt tầm nhìn + G1–G7 trong file này | Chờ Owner |
| D0-02 | Chốt Python + PySide6 + CCXT + MT5 + Telegram P0 | **Đề xuất chốt trong v1.1** |
| D0-03 | Điền mục 16 (số liệu cá nhân Owner) | Chờ Owner |
| D0-04 | Viết `AGENTS.md` + `mvp-capability-matrix.md` trỏ v1.1 | Sau khi duyệt D0-01 |
| D0-05 | Review ToS sàn dự định dùng bot | Owner |

Backlog code (chỉ mở sau D0): sẽ tách thành task D1-xx trong matrix — **chưa liệt kê để tránh bắt đầu code sớm**.

---

## 16. Thông số cá nhân Owner (điền trước D1)

> Không chặn việc duyệt kiến trúc; **chặn mở code D1** nếu còn trống mục bắt buộc.

| Hạng mục | Bắt buộc? | Giá trị Owner điền |
|---|---|---|
| Sàn/broker DEMO ưu tiên thử trước (vd. Binance testnet / MT5 demo / Paper) | Có | _…_ |
| Symbol + timeframe mặc định đầu tiên | Có | _…_ |
| Trần lỗ ngày / rủi ro mỗi lệnh (nếu khác mặc định mục 07) | Không | _…_ |
| Chat Telegram dùng báo cáo (cá nhân) | Có (trước khi exit D1) | tạo bot khi vào D1 |
| Có cần MT5 ngay trong D1 hay để D1.1? | Có | _…_ |
| Ngôn ngữ UI | Không (mặc định Tiếng Việt) | Tiếng Việt |

---

## 17. Rủi ro sản phẩm (solo + đa sàn)

| ID | Rủi ro | Giảm thiểu |
|---|---|---|
| P-01 | Hiểu nhầm “mọi sàn” = đã có đủ connector | UI ghi rõ nhóm A–E; allowlist |
| P-02 | Sàn CCXT khác nhau quirks (precision, hedge) | Contract test; bật dần allowlist |
| P-03 | Nhầm DEMO/LIVE | Badge + prefix Telegram + account tách |
| P-04 | Máy sleep khi còn vị thế | Chống sleep khi running; stop native |
| P-05 | MT5 terminal tắt | Health → L1 + Telegram |
| P-06 | ToS cấm API/bot | Review D0-05 |
| P-07 | Lệnh nguy hiểm từ Telegram nếu lộ chat | Whitelist chat id; mặc định tắt flatten |
| P-08 | Overfit AI | Shadow DEMO dài; không auto promote LIVE |

---

## 18. Quan hệ với Enterprise blueprint

| Chủ đề Enterprise | Desktop Solo v1.1 |
|---|---|
| FSM lệnh, risk số, AI 9 bước | **Giữ tinh thần / số liệu** |
| Kafka, K8s, Vault, dual-control, SaaS | **Bỏ** |
| MetaApi mặc định | **Không** — MT5 official |
| “1 adapter trước” | **Thay bằng** plugin + CCXT generic + Paper; ship dần |
| JWT login | **Không** |

---

## 19. Tiêu chí duyệt D0 (Owner ký)

Đánh dấu khi đồng ý — sau đó mới được phép tạo skeleton code:

- [ ] Đồng ý tầm nhìn mục 00 và mục tiêu G1–G7  
- [ ] Đồng ý “đa sàn” = **nền tảng adapter + CCXT/MT5/Paper**, không phải 200 connector ngày 1  
- [ ] Đồng ý DEMO/PAPER trước LIVE  
- [ ] Đồng ý Telegram là báo cáo P0  
- [ ] Đồng ý **Python 3.11+ + PySide6**, không Tauri/React giai đoạn này  
- [ ] Đã điền (hoặc chấp nhận điền ngay khi mở D1) mục 16  
- [ ] Hiểu đây chưa phải lời khuyên đầu tư; LIVE do Owner chịu trách nhiệm  

**Chữ ký Owner / ngày:** __________________

---

*Không phải lời khuyên đầu tư, tài chính hay pháp lý. Ứng dụng phục vụ tự doanh vốn riêng.*
