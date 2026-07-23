# App Auto-Trade AI — Personal Desktop (Solo) — v1.3

> Kiến trúc sản phẩm độc lập cho **một người, Windows desktop, không login**, tự giao dịch bằng vốn của chính mình.
>
> **Nguồn sự thật có tính quy phạm:** file này. Enterprise blueprint chỉ là tài liệu tham khảo, không được dùng để lấp chỗ thiếu hoặc ghi đè quyết định trong file này.
>
> **Trạng thái:** v1.3 — tối ưu và khoá tài liệu **trước khi code**. Chưa triển khai mã nguồn.

| | |
|---|---|
| **PHIÊN BẢN** | v1.3 — thu gọn MVP, chốt ranh giới runtime, bổ sung bất biến LIVE/OMS/Recovery/Risk và release gate |
| **ĐỐI TƯỢNG** | Hồ sơ pháp lý **(a)**: Owner chỉ tự giao dịch bằng vốn của chính mình; không quản lý vốn hay cung cấp tín hiệu cho người khác |
| **NỀN TẢNG** | Windows 11 x64 baseline; Windows 10 22H2 chỉ best-effort khi còn ESU |
| **AUTH** | Không đăng nhập tài khoản app; PIN local là safety interlock, không phải ranh giới chống người đã chiếm Windows account |
| **NGÔN NGỮ** | Một bản **CPython minor đã chứng nhận và pin** cho mỗi release (ứng viên D1: Python 3.14.x — xem ADR-D01) |
| **KẾT NỐI** | Adapter built-in + allowlist/chứng nhận theo sàn/market; external plugin để sau MVP |
| **BÁO CÁO** | Telegram là kênh báo cáo chính (bắt buộc từ MVP) |
| **CHƯA CODE** | Chỉ cập nhật tài liệu cho tới khi toàn bộ gate D0 ở mục 20 được duyệt |

### Lịch sử phiên bản (file này)

| Ver | Ngày | Thay đổi |
|---|---|---|
| v1.0 | 2026-07-23 | Profile desktop solo rút từ Enterprise |
| v1.1 | 2026-07-23 | Thống nhất: đa sàn (plugin), demo/live, Telegram bắt buộc, chốt Python-only; chi tiết mục tiêu trước code |
| v1.2 | 2026-07-23 | An toàn vận hành: Startup Recovery + KS persist (G3.6, 11.1), stop native bắt buộc LIVE (G3.5), PIN spec (ADR-D11), chuẩn hoá position/margin (G1.4); Paper fidelity (G2.3); logging local + Telegram queue (08); Alembic + auto-backup (ADR-D03); NTP check; tách D1a/D1b; Python 3.12+ |
| v1.3 | 2026-07-23 | Tối ưu trước code: file tự chứa; MVP một account/sàn; adapter built-in; pin runtime/packaging; bỏ HTTP nội bộ; nguồn sự thật theo domain; OMS crash-consistent; stop LIVE không override; recovery/recon đầy đủ; risk định lượng; Telegram an toàn; fault matrix và roadmap mới |

---

## 00. Tầm nhìn sản phẩm (một câu)

> Phần mềm desktop cá nhân giúp Owner **tự kết nối sàn/broker đã được hệ thống hỗ trợ và chứng nhận**, chạy bot có **risk + kill-switch**, nhận báo cáo/cảnh báo qua Telegram; Backtest và AI tự học trên máy chỉ được bổ sung sau khi đường giao dịch DEMO ổn định — không login, không SaaS, không phụ thuộc đội vận hành.

---

## 01. Mục tiêu thống nhất (chi tiết — Definition of Done sản phẩm)

Mỗi mục tiêu có tiêu chí “xong” đo được. Đây là hợp đồng phạm vi trước khi viết code.

### G1 — Đa sàn / tự kết nối (cốt lõi sản phẩm)

| # | Mục tiêu chi tiết | Tiêu chí xong |
|---|---|---|
| G1.1 | Lõi **không** hard-code một sàn. Mọi sàn đi qua **Broker Adapter Interface** thống nhất. | Thêm adapter built-in mới = thêm module + manifest + contract test; **không** sửa Strategy / Risk / OMS |
| G1.2 | Owner **tự kết nối** trong app (wizard), không cần sửa code. | Form: chọn loại adapter → nhập credential → Test connection → lưu (secret vào keyring) → chọn Demo/Live |
| G1.3 | Hỗ trợ theo **nhóm adapter**, mở rộng dần; không hứa mọi private API CCXT hoạt động giống nhau. | UI chỉ cho giao dịch trên adapter/exchange/market đã ship và đạt capability gate; mục “sắp có” không cho nhập credential |
| G1.4 | Chuẩn hoá symbol, timeframe, order, balance, margin và **risk exposure**, nhưng không làm mất semantics gốc. | Lưu venue/market/currency/contract/position-mode/leg/ticket/raw reference; Strategy dùng symbol nội bộ; Risk dùng exposure projection được suy ra |
| G1.5 | Kiến trúc cho phép nhiều account về sau; **D1 chỉ một account active tại một thời điểm**. | Multi-account chỉ mở sau khi adapter thứ hai qua contract test và không rò state/risk giữa account |

**Ý nghĩa “bất kể sàn nào”:**  
Không phải mọi sàn CCXT đều tự động đủ điều kiện giao dịch. Nghĩa là **hạ tầng có thể mở rộng**, còn D1 chỉ cho phép một exchange/market DEMO đã được allowlist và kiểm thử. Số lượng exchange CCXT hỗ trợ không phải cam kết về stop, client ID, sandbox, hedge mode hay private WebSocket.

### G2 — Demo / Paper / Live

| # | Mục tiêu | Tiêu chí xong |
|---|---|---|
| G2.1 | Mỗi account gắn đúng một **Trading Mode**: `DEMO` \| `PAPER` \| `LIVE` | Mode hiện rõ trên Dashboard, tray, mọi lệnh Telegram |
| G2.2 | `DEMO` = tài khoản demo của sàn/broker (MT5 demo, Binance testnet/demo, v.v.) | Credential demo tách biệt live; không trộn key |
| G2.3 | `PAPER` = mô phỏng deterministic, không gửi lệnh sàn; fill theo bid/ask khi có, fee + slippage cấu hình. Partial fill chỉ mô phỏng khi có dữ liệu phù hợp hoặc trong fault test được tiêm chủ động. | Cùng input + seed cho cùng kết quả; ghi rõ giới hạn fidelity, không suy diễn thanh khoản từ OHLC; 14 ngày chỉ là operational soak |
| G2.4 | `LIVE` bị hard-disable tới phase LIVE-readiness; sau đó chỉ mở bằng machine gate + PIN + gõ `LIVE`. | Audit ghi snapshot eligibility và thời điểm bật; thay adapter/credential/version/risk semantics làm mất eligibility |
| G2.5 | Mặc định xuất xưởng: chỉ cho phép tạo account `DEMO` hoặc `PAPER` | Live phải opt-in có chủ đích |

### G3 — An toàn vốn (không thương lượng)

| # | Mục tiêu | Tiêu chí xong |
|---|---|---|
| G3.1 | 100% hành động **tăng exposure** đi qua Risk và risk reservation, fail-closed. Hành động giảm rủi ro dùng safety validator `reduce-only/no-position-flip`, không bị chặn bởi limit entry. | Mọi submit có `risk_check_id`; exit khẩn cấp có audit + validator result |
| G3.2 | L1–L4 hoạt động từ UI; tray và Telegram chỉ cho Pause L1. L3/L4 chỉ kích hoạt local ở baseline. | Game-day DEMO: L3 đạt trạng thái flat xác nhận trong ≤30s khi market mở và tài sản thanh khoản; nếu không thể thì giữ L3 latched + SEV1 |
| G3.3 | OMS crash-consistent: persist intent + risk reservation + deterministic client ID trước network; sau khi transmission bắt đầu mà timeout thì `UNKNOWN`, không retry mù. | Fault test tại mọi biên I/O không tạo duplicate exposure trong capability đã chứng nhận |
| G3.4 | Recon startup + định kỳ: broker là sự thật cho exposure hiện tại; SQLite giữ intent/lịch sử bất biến. | Phát hiện local/broker orphan, fill bị lỡ, stop thiếu; account bị L2/SAFE_LOCK đến khi xử lý |
| G3.5 | **Stop native bắt buộc, không có override cho LIVE:** entry LIVE chỉ hợp lệ khi broker giữ attached/contingent stop bao phủ mọi fill, kể cả partial/late fill; ưu tiên stop-market, `reduceOnly/closeOnly` đúng semantics. | Thiếu/reject/cancel/undersized protection → chặn entry, L3 reduce-only flatten và SEV1; alert đơn thuần không được coi là xử lý |
| G3.6 | **Startup Recovery:** khôi phục KS, query mọi order non-terminal/open/conditional, ingest executions theo cursor có overlap, recon position legs/balance/margin/protection rồi mới trade. | Recovery thiếu dữ liệu, auth fail, pagination chưa xong hoặc state stale → account tiếp tục locked |
| G3.7 | **LIVE eligibility** là state máy tính được theo account + instrument, không phải checklist tự khai. | Chỉ `ELIGIBLE` khi mode xác định, adapter tuple đã chứng nhận, risk fresh, clock hợp lệ, recovery sạch, protection kiểm chứng được |

### G4 — Giao dịch & AI

| # | Mục tiêu | Tiêu chí xong |
|---|---|---|
| G4.1 | MVP: 1 strategy rule-based, 1 account active, 1 symbol + timeframe trên PAPER rồi CCXT DEMO | Deterministic tests + fault matrix pass; soak ≥14 ngày chỉ chứng minh vận hành, không chứng minh lợi nhuận |
| G4.2 | Sau MVP và sau Backtest deterministic: AI sinh xác suất hiệu chỉnh + giải thích nhẹ | Walk-forward/out-of-sample + shadow DEMO; không gắn LIVE chỉ vì đủ số ngày |
| G4.3 | Retrain chạy process riêng, không tranh tài nguyên trading; promote thủ công | Model/data/version truy vết được; rollback drill pass trước khi dùng vốn thật |

### G5 — Báo cáo & điều khiển qua Telegram (bắt buộc)

| # | Mục tiêu | Tiêu chí xong |
|---|---|---|
| G5.1 | Owner cấu hình Bot Token + private Chat ID + Owner User ID trong Settings (token qua keyring) | Nút “Gửi tin thử” thành công; inbound từ sai chat/user bị reject và audit |
| G5.2 | Báo cáo đẩy (push) theo sự kiện — không chỉ log file | Đủ các loại ở bảng Telegram (mục 08) |
| G5.3 | Digest cuối ngày là P0; digest tuần để sau MVP. | P&L, số lệnh, drawdown, KS, adapter health; gắn thời điểm dữ liệu |
| G5.4 | Lệnh D1: `/status`, `/pnl`, `/pause`; không remote resume/flatten/unlock. | Persist/deduplicate `update_id`; reject command quá TTL; PIN/credential không bao giờ đi qua Telegram |
| G5.5 | Mọi tin Telegram gắn `mode` (DEMO/PAPER/LIVE) và `account` | Tránh nhầm demo với live |

### G6 — Desktop một người, không login

| # | Mục tiêu | Tiêu chí xong |
|---|---|---|
| G6.1 | Mở app → Dashboard; không form đăng nhập cloud | App chỉ vào trạng thái trade-enabled sau recovery; UI vẫn mở được khi SAFE_LOCK |
| G6.2 | PIN local cho: bật LIVE, nới risk, resume/unlock, xem/xoá secret. Pause/Flatten local luôn khả dụng và không bị PIN lockout chặn. | Test sai PIN/lockout/reset; reset đưa mọi LIVE account về locked và tắt remote mutation |
| G6.3 | System tray: trạng thái, P&L ngày, Pause (L1), mở app | Không có Resume/Flatten remote từ tray; Quit có policy rõ khi còn vị thế |
| G6.4 | Single-instance lock | Không chạy 2 process trading |

### G7 — Trải nghiệm “tự kết nối” (UX)

Wizard **Kết nối sàn** (màn Broker Hub):

1. Chọn **nhóm đã ship**: Paper nội bộ / Crypto (CCXT); MT5 và chứng khoán hiện “sau MVP”  
2. Chọn **sàn cụ thể đã allowlist/chứng nhận**; không hiển thị toàn bộ `ccxt.exchanges` như thể đã hỗ trợ trading  
3. Chọn **mode**: DEMO / LIVE (LIVE bị khoá tới khi đủ điều kiện)  
4. Nhập credential theo template adapter (API key, secret, password, server MT5, …)  
5. **Test connection** → hiện external account ID, mode detected, market, số dư và quyền `VERIFIED / DENIED / UNKNOWN`  
6. Key có quyền withdraw đã biết → từ chối LIVE; quyền không introspect được → ghi UNKNOWN + checklist thủ công  
7. Lưu → hiện trong danh sách account → gán strategy  

Owner **không** cần biết code để thêm một sàn thuộc nhóm đã ship.

---

## 02. Ngoài phạm vi (cố ý)

- Login / JWT / RBAC / multi-tenant / SaaS / App Store cloud account  
- Dual-control 2 người, màn Approvals enterprise  
- Kafka, Kubernetes, Vault HA, multi-region DR, on-call SRE  
- “Kết nối mọi sàn trên trái đất” trong ngày đầu nếu chưa có adapter (chỉ hứa **nền tảng mở rộng**)  
- External Python plugin/drop-in adapter trong D1  
- Local HTTP API/FastAPI trong MVP  
- Multi-account active, MT5, Backtest UI và mọi AI/ML dependency trong D1  
- Auto-update và LIVE không giám sát khi chưa có core service/dead-man độc lập  
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

### ADR-D01 — Một CPython minor được pin cho mỗi release

**Quyết định:** Toàn bộ trading core và UI dùng cùng một CPython minor. D1 đánh giá **Python 3.14.x**; chỉ chốt sau compatibility smoke test trên Windows sạch với toàn bộ dependency và bản đóng gói. Release metadata dùng range đóng, ví dụ `>=3.14,<3.15`, cùng lockfile có hash; không dùng range mở `3.12+`.

Nâng minor Python là một thay đổi release có kiểm thử migration, backup/restore, adapter contract và packaged E2E. ML ở phase sau không được kéo dependency vào D1 hoặc buộc D1 chọn runtime cũ.

| Thành phần | Thư viện |
|---|---|
| UI desktop | **PySide6 (Qt 6)** — một runtime, tray/native dialog tốt; không tuyên bố nhẹ hơn nếu chưa benchmark bản đóng gói |
| Chart D1 | **pyqtgraph**; không nhúng WebEngine trong MVP |
| Local API | **Không có trong MVP**; module gọi in-process |
| Async / I/O | `asyncio`; một command owner serialize OMS theo account; SDK blocking chạy trong bounded dedicated executor |
| Crypto | **CCXT**: REST sync/async và namespace WebSocket `ccxt.pro` trong cùng package; availability kiểm tra theo method/exchange |
| Forex/CFD | **MetaTrader5 official** ở D2, không cài trong D1 |
| DB | SQLite WAL + SQLAlchemy 2.x + Alembic |
| ML | **Không cài trong D1**; scikit-learn/XGBoost/LightGBM/Optuna chỉ là ứng viên khi vào phase AI |
| Secret | `keyring` (Windows Credential Manager) |
| Telegram | **python-telegram-bot**; không tự viết polling/dedup từ đầu |
| Đóng gói | **PyInstaller `onedir`** + installer Windows; MVP cập nhật thủ công |
| Test / quality | pytest, ruff; type-check tăng dần theo ranh giới domain |

**Lý do chọn:** một runtime, ít toolchain, đúng hệ sinh thái broker/ML và phù hợp bảo trì solo. Tiêu chí là độ ổn định vận hành, không phải khẩu hiệu dung lượng/RAM.

**Không dùng ở baseline:** Electron, WebEngine, FastAPI, Kubernetes, Kafka, external plugin loader.

### ADR-D02 — Không login app; PIN chỉ là safety interlock

Mở app = vào Dashboard. PIN giảm thao tác nhầm, không bảo vệ trước malware hoặc người đã kiểm soát cùng Windows account. Windows account, BitLocker và cập nhật hệ điều hành là lớp bảo vệ máy.

### ADR-D03 — SQLite

DB local tại `%LOCALAPPDATA%/AutoTradeAI/` (hoặc thư mục `data/` lúc dev). Schema migration bằng Alembic từ D1.

- Một DB writer; bật `journal_mode=WAL`, `synchronous=FULL`, `foreign_keys=ON`, bounded `busy_timeout`.
- Intent, risk reservation, audit event và outbox liên quan phải commit cùng transaction trước side effect ra broker.
- Disk full, corruption, migration fail hoặc mandatory commit fail → `SAFE_LOCK`, chặn tăng exposure.
- Trước migration luôn tạo snapshot. Backup lịch dùng SQLite backup API vào file tạm → `integrity_check` → atomic rename; giữ mặc định 7 bản. `VACUUM INTO` chỉ là lựa chọn snapshot compact và cũng phải kiểm tra file đích.
- Restore luôn khởi động locked và chạy full recovery/recon trước trade. Snapshot cùng ổ chỉ chống lỗi logic/corruption; backup off-device mã hoá là tuỳ chọn sau MVP.

### ADR-D04 — Bus nội bộ

Không Kafka. SQLite `events/outbox` là durable record; `asyncio.Queue` chỉ là wake-up signal và có thể tái tạo sau restart.

Phân định nguồn sự thật:

- **Broker:** execution, open order, position và balance hiện tại bên ngoài.
- **SQLite:** intent, FSM app, fill đã ingest, risk-check/reservation, audit và notification outbox.
- **JSONL:** chẩn đoán; không phải ledger và không được dùng tự động sửa state.

### ADR-D05 — MT5

Để D2. Official `MetaTrader5` kết nối terminal cùng Windows; call được serialize, không giả định thread-safe. Một Python module chỉ sở hữu một terminal/account active; nhiều MT5 account đồng thời cần process/terminal riêng và thiết kế lại ownership.

Python API không cung cấp trading-session windows tương đương `SymbolInfoSessionTrade`; không lấy lịch phiên từ `symbol_info()`. Adapter phải có calendar đã kiểm chứng hoặc bridge MQL5 riêng. Disconnect/auth fail → L2 account + Telegram; protective stop phía broker vẫn được giữ.

### ADR-D06 — Secret

Chỉ `keyring`. UI chỉ hiện masked. Không ghi plaintext vào SQLite/config/log/crash report; credential fields trong manifest bắt buộc đánh dấu `secret` và đi qua redaction allowlist.

**Lưu ý cho Owner:** keyring gắn với máy/user Windows — **chuyển sang PC mới là mất toàn bộ credential**, phải nhập lại API key từng sàn. UI Settings ghi rõ điều này; không làm tính năng export secret (rủi ro > lợi ích).

### ADR-D07 — Reporting currency

Mặc định USD; tuỳ chọn hiển thị VND, FX lưu theo sự kiện. Nguồn hiển thị có thể cache theo ngày và không dùng cho Risk.

Risk một account dùng equity/collateral currency do broker cung cấp cùng quote/FX fresh đã kiểm chứng. Khi mở multi-account mới bổ sung portfolio valuation, stale policy và haircut; không mặc định `1 USDT = 1 USD`.

### ADR-D08 — Đóng gói

PyInstaller `onedir` → installer Windows x64. Không auto-update ở MVP. Update bị chặn khi trading active, tạo pre-migration backup, có rollback binary/DB khi migration fail và phải pass clean-machine install/uninstall/data-retention test. Code signing chỉ bắt buộc nếu phân phối ra ngoài máy Owner.

### ADR-D09 — Adapter interface là xương sống; plugin ngoài để sau

Mọi kết nối sàn = implementation của interface mục 05. D1 chỉ load adapter built-in. CCXT là adapter generic nhận `exchange_id`, nhưng chỉ tuple exchange/market/mode đã chứng nhận mới được trade. External plugin SDK chỉ thiết kế sau khi ít nhất hai họ adapter built-in chứng minh interface.

### ADR-D10 — Telegram là kênh báo cáo hạng mục P0

Không hoãn sau MVP. Không có Telegram cấu hình và test thành công thì chưa đạt exit D1; Telegram không phải nguồn audit duy nhất.

### ADR-D11 — PIN local (spec)

- Lưu **hash Argon2id** (salt riêng) trong DB — không plaintext, không keyring (PIN là knowledge factor, không phải secret máy).
- Sai **5 lần liên tiếp** → lockout 15 phút (nhân đôi mỗi chu kỳ sai tiếp); mọi lần sai ghi `audit_events` + Telegram SEV2.
- PIN bắt buộc khi bật LIVE, nới risk, resume/unlock hoặc xem/xoá secret; **không** chặn Pause/Flatten local.
- Quên PIN: không reset qua email. Local recovery xoá verifier bằng một quy trình được audit ở lần mở kế tiếp; mọi LIVE eligibility bị thu hồi, KS tối thiểu L2 và mọi remote mutation bị tắt. Đây không phải cơ chế chống người sửa trực tiếp DB.

### ADR-D12 — Đồng hồ hệ thống & watchdog

- Timeout/cooldown dùng monotonic clock; audit/event dùng UTC.
- Lúc startup và định kỳ, so local clock với broker/server time khi adapter hỗ trợ. Ngưỡng là adapter-specific và nhỏ hơn signing window an toàn; vượt ngưỡng → chặn tăng exposure, không chỉ cảnh báo.
- Chống sleep chỉ best-effort. Sau sleep/resume, network change hoặc wall-clock jump phải chạy recovery subset và refresh quote/account state trước trade.
- D1 không có process watchdog; stop native là tuyến phòng thủ cuối, không bảo đảm giá khớp. Mọi LIVE trước core service/dead-man độc lập được coi là **attended-only**.

### ADR-D13 — Một process ở MVP, không localhost API

Headless và GUI là hai entry point loại trừ nhau của cùng composition root; chỉ một process giữ single-instance lock và sở hữu adapter/OMS/DB writer. UI chạy trên Qt main thread; command vào core qua hàng đợi có thứ tự. Không mở HTTP port.

Quit khi còn position/order phải hiển thị state thực tế và yêu cầu xác nhận local; quit dừng strategy nhưng không xoá protective order. LIVE không giám sát chỉ được xem xét sau khi tách core service và có heartbeat/dead-man độc lập.

### ADR-D14 — LIVE eligibility và capability certification

Eligibility key: `app_version + adapter_version + exchange/broker + API endpoint + market + account_mode + instrument + order/protection capabilities + risk_semantics_version`.

`UNKNOWN` ở bất kỳ trường bắt buộc nào → không LIVE. Đổi key/credential/endpoint/library version/instrument metadata hoặc restore DB → eligibility về `LOCKED`, phải chạy lại gate tương ứng.

---

## 04. Kiến trúc tổng thể

```
┌──────────────────────────────────────────────────────────┐
│ One process / one composition root                        │
│                                                          │
│ PySide6 UI (hoặc headless entry point — không chạy cùng) │
│ Dashboard · Broker Hub · Strategy · Risk/Kill             │
│ Live Monitor · History · Settings · Tray                  │
│                         │ ordered in-process commands      │
│ Trading Core            ▼                                 │
│ Market → Features → Strategy → Risk reservation → OMS    │
│                                      │                    │
│ Broker Hub → Built-in Registry → Paper | CCXT certified  │
│                                      │                    │
│                   Fills/Open Orders/Positions → Recon    │
│ SQLite: intent/FSM/audit/outbox · keyring: credentials   │
│ Notify fan-out → Telegram + Windows Toast                 │
└──────────────────────────────────────────────────────────┘
```

**Đường găng:** Strategy → Risk reservation → durable intent commit → OMS → Adapter.

- Trước khi transmission bắt đầu: dependency/risk/persist fail → fail-closed, không gửi.
- Sau khi transmission có thể đã bắt đầu: timeout → delivery `MAY_HAVE_BEEN_ACCEPTED` + order `UNKNOWN`; giữ reservation, query/reconcile, tuyệt đối không coi là reject hoặc gửi lại mù.
- Hành động reduce-only khẩn cấp đi qua no-position-flip validator và có rate-limit lane ưu tiên.

---

## 05. Broker Adapter — hạ tầng “tự kết nối mọi sàn hỗ trợ”

### 05.1 Interface bắt buộc (mọi adapter)

```
connect() → AccountIdentity
disconnect()
health() → HealthSnapshot

list_instruments() / get_instrument_spec(symbol)
get_capability_snapshot(account, market, symbol)
subscribe_market_data() | poll_market_data()
get_ohlcv(symbol, timeframe, since, limit)

place_order(intent_with_protection) → SubmitResult
cancel_order(client_order_id | broker_order_id) → CancelResult
get_order(client_order_id | broker_order_id)
list_open_orders(include_conditional=True)
get_executions(since_cursor, overlap)
get_positions(preserve_legs=True)
get_balance() / get_margin_state()
```

Các result phải phân biệt delivery certainty (`NOT_SENT`, `MAY_HAVE_BEEN_ACCEPTED`, `CONFIRMED`) với broker order state. Health là structured snapshot gồm auth, endpoint, clock, market-data age, private-data age và rate-limit state; không chỉ là boolean.

Kèm:

- Error taxonomy nội bộ; raw exception được redaction trước log/UI.
- Rate-limit lane ưu tiên cho cancel, protection, recon và flatten.
- Instrument spec gồm base/quote/settlement currency, contract size, linear/inverse, tick/lot/min-notional, leverage/margin mode, position mode và order flags.
- Raw broker reference được giữ để audit; normalized exposure là projection, không thay thế position legs.

**Client order ID:** OMS persist ID nội bộ trước network; adapter biến đổi deterministic sang charset/length của broker và lưu hai chiều. LIVE chỉ hợp lệ nếu broker hỗ trợ unique client ID + lookup/dedup tương đương đã được contract test. Mapping local sau khi gửi không tự tạo idempotency.

**Fill:** ingest theo broker execution/trade ID có unique constraint; cùng fill nhận lại nhiều lần chỉ có một hiệu lực.

### 05.2 Manifest adapter (đăng ký)

Mỗi adapter khai báo:

| Field | Ví dụ |
|---|---|
| `adapter_id` | `ccxt`, `mt5`, `paper`, `ibkr` (sau) |
| `display_name` | “Crypto (CCXT)” |
| `credential_schema` | JSON form fields + cờ `secret`, validation, redaction |
| `modes_declared` | PAPER, DEMO, LIVE (chỉ khai báo; không đồng nghĩa đã chứng nhận) |
| `markets` | crypto / forex / stocks |
| `capability_declared` | spot, swap, client_id_lookup, attached_stop, conditional_orders, … |
| `adapter_api_version` | version contract của app |
| `setup_help` | text hướng dẫn Owner lấy key / mở demo |

UI đọc registry để render form nhưng chỉ bật tính năng theo **runtime capability snapshot + certification record**. Capability có thể khác nhau giữa spot/swap, account mode và từng symbol.

### 05.3 Nhóm hỗ trợ (roadmap kết nối)

| Nhóm | Phạm vi | Cách Owner tự nối | Phase ship |
|---|---|---|---|
| **A — Paper** | Mô phỏng deterministic | Một click “Tạo tài khoản Paper” | D1a |
| **B — Crypto qua CCXT** | Một exchange + market DEMO Owner chọn ở mục 16 | Wizard credential + connection/capability test | D1b |
| **C — MetaTrader 5** | Forex/CFD/vàng qua một terminal/account | Login + password + server; DEMO trước | D2 hoặc sau |
| **D — Adapter thứ hai / multi-account** | CCXT exchange thứ hai hoặc MT5 | Qua cùng contract suite | D2 |
| **E — Chứng khoán** | IBKR / Alpaca, … | Adapter built-in riêng | D4+ |
| **F — External plugin** | Adapter ngoài bản cài | SDK versioned + trust/loading policy | D5+ |

**Allowlist D1:** đúng một `exchange_id + market + sandbox endpoint` do Owner chốt ở mục 16. Settings không thể tự mở trading cho exchange khác; exchange chưa chứng nhận chỉ được phép market-data read-only hoặc PAPER.

**Không** hard-code logic Binance trong Strategy. Chỉ `adapter_id=ccxt` + `exchange_id=binance`.

### 05.4 Demo theo từng họ

| Họ | Cách DEMO |
|---|---|
| CCXT | Testnet/sandbox endpoint đã chứng nhận; nếu không có demo đáng tin cậy → Paper + live data read-only |
| MT5 | Tài khoản demo từ broker (server demo) |
| Paper | Luôn demo/mô phỏng |

UI phải hiện bằng chữ + icon + màu: `PAPER`, `DEMO`, `LIVE`; không dựa riêng vào màu.

### 05.5 Quy trình chứng nhận adapter/exchange

1. Implement interface + manifest; pin adapter/library/API version.  
2. Pass contract suite: instrument precision, place/status/cancel, direct fill, partial/late fill, client-ID lookup, fee/margin, pagination, conditional/protective order.  
3. Pass fault suite: timeout trước/sau send, duplicate/out-of-order execution, rate-limit, disconnect và restart.  
4. Nối DEMO thật, chạy đủ lifecycle + soak theo mục 18; lưu evidence.  
5. Ghi certification record cho đúng tuple; mới bật DEMO trading.  
6. LIVE là certification riêng, không kế thừa tự động từ DEMO.

Upgrade CCXT/adapter, đổi endpoint, credential scope, market hoặc instrument metadata làm certification liên quan hết hiệu lực.

---

## 06. Chế độ tài khoản & an toàn LIVE

```
PAPER  → không gửi lệnh sàn
DEMO   → gửi lệnh tài khoản demo/testnet
LIVE   → tiền thật (PIN + xác nhận)
```

Chuyển DEMO→LIVE: không đổi mode trên cùng credential record. Bắt buộc tạo account LIVE riêng, external account ID riêng, eligibility riêng.

### 06.1 Machine gate bắt buộc

- [ ] App/adapter/exchange/market/instrument tuple có LIVE certification còn hiệu lực.  
- [ ] `account_mode_detected = LIVE`, endpoint và external account ID khớp cấu hình.  
- [ ] Client-ID lookup/dedup, open/conditional orders và execution cursor đã contract-test.  
- [ ] Attached broker-side protection đáp ứng G3.5; không có override.  
- [ ] Startup Recovery + continuous Recon sạch; KS không active ngoài L0.  
- [ ] Risk config, instrument metadata, execution quote, margin và clock đều fresh.  
- [ ] Fault matrix LIVE ở mục 18 pass trên DEMO tương ứng.  
- [ ] Telegram SEV1 test pass; notification outbox/storage healthy.  
- [ ] API key đã biết có withdraw → fail; permission UNKNOWN phải có manual attestation và dedicated subaccount/key.

### 06.2 Xác nhận Owner

- [ ] Đã xem evidence soak/fault test; hiểu 14 ngày không chứng minh lợi nhuận.  
- [ ] Đã chốt risk limit và capital cap cho đúng account/instrument.  
- [ ] Đã test Pause/Flatten local.  
- [ ] Hiểu baseline LIVE là attended-only.  
- [ ] Nhập PIN và gõ chính xác `LIVE`; audit lưu eligibility snapshot.

Scope LIVE đầu tiên: đúng một account, một market và một symbol đã chứng nhận. Không external plugin, không multi-account.

---

## 07. Risk & Kill-switch

### Limit mặc định đề xuất (Owner phải xác nhận)

Các số dưới đây là guardrail kỹ thuật, không phải lời khuyên đầu tư. LIVE luôn cần Owner xác nhận lại.

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
| Kelly | **Tắt ở D1**; chỉ xem xét sau AI calibration/walk-forward |
| Ngoài session | Không entry mới |

### 07.1 Quy tắc tính Risk

- Tất cả money/price/quantity/rate dùng `Decimal` hoặc integer minor units theo contract; không dùng binary float cho quyết định tiền.
- `risk_per_order` = worst-case loss tới stop + fee + slippage + gap stress, sau khi làm tròn theo lot/tick/min-notional rồi phải kiểm tra lại.
- Adapter cung cấp contract-tested notional/P&L/margin cho spot, linear/inverse contract và MT5 lot. Giá trị `UNKNOWN` chặn tăng exposure.
- Risk bao gồm position hiện tại + working orders + `UNKNOWN/MAY_HAVE_BEEN_ACCEPTED` + candidate reservation; check và reservation atomic theo account.
- Daily/rolling loss dùng equity thay đổi đã loại deposit/withdrawal, gồm realized + unrealized P&L, fee, funding/swap; lưu timezone và mark source.
- Global/portfolio exposure chưa tồn tại ở D1; phải thiết kế trước khi bật account thứ hai.

### 07.2 Freshness và session

- **Execution quote D1 crypto:** bid/ask age >5s → không tăng exposure. LIVE có thể đặt ngưỡng chặt hơn theo certification, không nới hơn nếu chưa test.
- **Signal candle:** chỉ dùng candle đã đóng; candle mới nhất phải đúng expected close, grace tối đa `min(10% timeframe, 60s)`.
- **Account/instrument state:** balance, margin, permission và instrument metadata quá TTL do certification quy định → không tăng exposure.
- **Session calendar:** crypto 24/7 vẫn phải tôn trọng maintenance/market status; MT5 dùng calendar/bridge riêng theo ADR-D05; thiếu calendar → fail-closed entry.
- **Kill-switch persist:** mức KS hiện tại luôn ghi DB; restart app không tự hạ mức (xem G3.6).

### Kill-switch

| Mức | Hành động | Resume |
|---|---|---|
| L1 | Pause exposure-increasing entry; vẫn quản lý protection/exit | D1 chỉ resume local + PIN sau khi trigger hết |
| L2 | Huỷ **exposure-increasing** pending; giữ protective orders; chặn entry | Local + PIN, recovery/recon sạch |
| L3 | Cancel entry → reduce-only flatten → reconcile lặp tới flat; giữ protection tới khi flat | Activation không cần PIN; resume local + PIN sau post-check |
| L4 | L3 + app lockdown, thu hồi LIVE eligibility | Local; unlock + PIN + gõ `UNLOCK` + chạy lại gate |

- Effective KS tại một scope là mức cao nhất của mọi trigger đang active; clear một trigger không tự hạ trigger khác.
- L3/L4 latched qua restart. Cancel/flatten timeout hoặc late fill giữ L3 và tiếp tục reconcile; không tuyên bố thành công chỉ vì đã gửi request.
- Emergency action có priority rate-limit lane và no-position-flip validator.
- Telegram chỉ được kích hoạt L1 `/pause`; không resume/flatten/unlock.

---

## 08. Telegram — báo cáo chi tiết

### Cấu hình

- Bot Token + đúng một private Chat ID + Owner User ID  
- Token trong keyring; không log URL/header chứa token  
- Múi giờ báo cáo (mặc định giờ máy / giờ Việt Nam cấu hình được)  
- Ngôn ngữ tin nhắn: **Tiếng Việt** (mặc định)
- Long polling chỉ một process; persist `update_id`, accepted/rejected command đều audit; command TTL mặc định 60s

### Sự kiện đẩy ngay

| Sự kiện | Mức | Nội dung tối thiểu |
|---|---|---|
| Bot start/stop | info | version, accounts connected |
| Kết nối adapter OK/FAIL | info/SEV2 | adapter, account, mode |
| Lệnh filled / rejected | info | symbol, side, qty, price, mode |
| Risk reject | info | lý do limit |
| Kill-switch đổi mức | SEV1/2 | level, scope, lý do |
| Recon break | SEV1 | lệch gì, giá trị |
| Recovery fail / SAFE_LOCK | SEV1 | account, bước lỗi, state giữ lại |
| LIVE protection thiếu/hỏng | SEV1 | account, symbol, qty chưa bảo vệ, hành động flatten |
| Disk/DB/outbox unhealthy | SEV1 | component, entry đã bị khoá hay chưa |
| Feed stale / MT5 disconnect | SEV2 | symbol/account |
| Model rollback | SEV1 | version cũ ← mới |
| Bật LIVE | SEV1 | account id masked |

### Digest định kỳ

| Digest | Nội dung |
|---|---|
| Cuối ngày | P&L ngày, số lệnh thắng/thua, max DD ngày, trạng thái KS, health |
| Cuối tuần | Sau MVP: P&L tuần, equity change, top symbol, cảnh báo mở |

### Lệnh Telegram (mặc định an toàn)

| Lệnh | Mặc định | Ghi chú |
|---|---|---|
| `/status` | Bật | equity, mode, KS, kết nối |
| `/pnl` | Bật | P&L ngày |
| `/pause` | Bật | = L1 global hoặc account chỉ định |
| `/resume_l1` | **Không có ở D1** | resume local + PIN |
| `/flatten` | **Không có ở baseline** | chỉ local; không có “dangerous commands” toggle |

Mọi update được deduplicate. Chỉ nhận command từ đúng private chat + user ID; command cũ hơn TTL hoặc không đúng actor bị reject và ghi `audit_events`. PIN/credential không bao giờ được yêu cầu qua chat.

### Độ tin cậy kênh báo cáo

- Telegram sập/mất mạng: notification vào SQLite outbox trong cùng transaction với event nguồn; gửi at-least-once, exponential backoff có jitter, tôn trọng `Retry-After`, message có event ID để dedup.
- Queue phải bounded theo retention; permanent 4xx vào dead-letter và hiện trên Dashboard. Không dùng cam kết tuyệt đối “SEV1 không bao giờ drop” khi disk/DB có thể hỏng.
- Khi LIVE attended-only mà outbox/storage unhealthy, chặn tăng exposure và bắn Windows Toast. Telegram không chứng minh Owner đã đọc tin.
- JSONL có cấu trúc tại `%LOCALAPPDATA%/AutoTradeAI/logs/`, rotate ngày, giữ mặc định 30 ngày, redaction bắt buộc. SQLite audit là record app; JSONL chỉ chẩn đoán.

---

## 09. UI desktop — màn hình

| Màn | Phase | Việc |
|---|---|---|
| **Dashboard** | D1c | Equity, P&L, KS, recovery/outbox/adapter health của account active |
| **Broker Hub** | D1c | Paper + đúng một CCXT DEMO đã allowlist; Test/Disconnect/capability result |
| **Kill-switch** | D1c | L1–L4 luôn hiện; Pause/Flatten local không bị PIN lockout chặn |
| **Live Monitor** | D1c | Quote age, tín hiệu, order/delivery state kể cả UNKNOWN, fills, protection |
| **Strategy** | D1c | Một rule strategy; tham số + hard risk ceiling không thể bị UI ghi đè |
| **History** | D1c | Intent, risk-check, order, fill, audit; tra cứu correlation/client ID; CSV |
| **Settings** | D1c | PIN, Telegram, certified allowlist, currency, autostart, backup |
| **Tray** | D1c | Status, P&L, Pause, Open, Quit theo policy ADR-D13 |
| **Backtest** | D3 | Chỉ tạo khi engine deterministic sẵn sàng; không scaffold màn rỗng ở D1 |
| **AI Center** | D4 | Chỉ tạo cùng model governance; không cài ML dependency ở D1 |

UI invariant:

- Mode + account + endpoint hiển thị bằng text/icon/màu trên mọi màn có hành động trade.
- Dữ liệu stale phải hiện tuổi dữ liệu, không chỉ badge “offline”.
- UI không gọi adapter hoặc sửa bảng trading trực tiếp; mọi mutation đi qua ordered core command.
- Nút kích hoạt L3 cần thao tác xác nhận có chủ đích nhưng không yêu cầu PIN; resume/nới risk mới yêu cầu PIN.

---

## 10. Module & phase

| Module | Phase | Exit chính |
|---|---|---|
| Domain types + Clock/ID ports | D1a | UTC/monotonic/Decimal deterministic; không broker type rò vào Strategy |
| SQLite journal + migration + audit/outbox | D1a | Atomic intent/reservation/outbox; restart và backup/restore tests |
| Fake broker + Paper adapter | D1a | Toàn FSM, partial/late fill và fault injection deterministic |
| Market / Feature / một Strategy rule | D1a | Chỉ closed candle; duplicate/missing/out-of-order data tests |
| Risk + Kill-switch | D1a | Reservation atomic; KS persist/scope/flatten validator tests |
| OMS + Fill ledger + Recon + Recovery | D1a | Crash-boundary matrix pass; state hội tụ về fake broker |
| Telegram + Toast + JSONL | D1a | Outbox retry/dedup; `/status` `/pnl` `/pause`; redaction tests |
| CCXT adapter + một DEMO allowlist | D1b | Contract/fault suite + real DEMO lifecycle/soak |
| PySide6 UI tối thiểu | D1c | Các màn D1 ở mục 09; UI không bypass core |
| PyInstaller installer + operations | D1c | Clean-machine install, single-instance, sleep/resume, backup/restore, manual upgrade |
| LIVE-readiness gate | D1.1 riêng | Tất cả mục 06 + fault matrix LIVE pass; Owner ký riêng |
| MT5 hoặc adapter thứ hai + multi-account | D2 | Contract suite; process ownership; không cross-account state leak |
| Backtest/replay | D3 | Same strategy logic, no look-ahead, repeatable result |
| AI shadow / retrain | D4 | Model governance + manual promotion/rollback drill |
| External plugin SDK | D5+ | Version/trust/loading/packaged compatibility policy |

---

## 11. Vòng đời lệnh & recovery (quy phạm trong file này)

```
CREATED
  ├─→ RISK_REJECTED
  └─→ RESERVED → SUBMITTING

SUBMITTING
  ├─→ ACKNOWLEDGED | FILLED | REJECTED
  └─→ UNKNOWN                    # transmission có thể đã xảy ra

ACKNOWLEDGED
  ├─→ PARTIALLY_FILLED → FILLED
  ├─→ CANCEL_REQUESTED
  └─→ CANCELED | REJECTED | EXPIRED

CANCEL_REQUESTED
  ├─→ CANCELED | FILLED | PARTIALLY_FILLED
  └─→ CANCEL_UNKNOWN

UNKNOWN | CANCEL_UNKNOWN
  └─→ query + executions/open-order reconciliation → trạng thái broker thực
```

Delivery certainty là trục riêng: `NOT_SENT → SENDING → CONFIRMED | MAY_HAVE_BEEN_ACCEPTED`. Không suy ra order state chỉ từ transport result.

Quy tắc:

- Fill là immutable event, unique theo `(account_id, broker_execution_id)`. Order có thể nhận late fill trong race với cancel.
- Mọi transition dùng compare-and-set/monotonic guard; response cũ không được hạ state đã tiến xa hơn.
- `UNKNOWN` hoặc `CANCEL_UNKNOWN` luôn giữ risk reservation cho tới khi query/recon chứng minh exposure thực.
- Không tự re-submit request có thể đã transmission. “Exactly once” không được hứa chung; mục tiêu là không tạo duplicate exposure trong capability/fault matrix đã chứng nhận.
- L2 không cancel protective order. Protection có lifecycle/link riêng với position leg và phải cập nhật quantity khi partial fill.

### 11.1 Durable submit protocol

1. Validate closed signal, instrument spec, execution quote, account/margin freshness.  
2. Trong một SQLite transaction: tạo intent/client ID → risk-check → reserve exposure → state `RESERVED` → audit/outbox.  
3. Commit thành công mới chuyển `SUBMITTING` và gọi adapter. Mandatory commit fail → không send.  
4. Adapter dùng deterministic broker client ID.  
5. Ack/reject/direct fill được persist idempotently cùng audit/outbox.  
6. Timeout sau khi transmission bắt đầu → `UNKNOWN/MAY_HAVE_BEEN_ACCEPTED`; không giải phóng reservation, không retry mù.  
7. Query by client ID + executions/open orders; adapter không có cơ chế này không đủ LIVE eligibility.

### 11.2 Startup Recovery (bắt buộc trước khi trade)

Kịch bản: app crash, mất điện, Windows update/sleep hoặc process bị kill ở bất kỳ biên I/O nào.

1. Vào `RECOVERING`; chặn tăng exposure; load KS đã persist và không tự hạ.  
2. Kiểm tra DB/schema/integrity; mandatory failure → `SAFE_LOCK`.  
3. Connect account, xác minh endpoint/mode/external ID/clock/capability.  
4. Load mọi local order non-terminal, reservation và durable execution cursor.  
5. Fetch có pagination: broker open + conditional orders, executions từ cursor có overlap, positions giữ từng leg/ticket, balance/margin và protective orders.  
6. Deduplicate fills; correlate cả client/broker ID; phân loại local orphan, broker/manual orphan, missing/undersized protection và state conflict.  
7. Broker thắng cho exposure hiện tại, nhưng không overwrite/xoá intent/fill/audit lịch sử; adjustment có provenance riêng.  
8. Effective KS = mức cao nhất giữa persisted trigger và trigger mới. LIVE thiếu protection → L3 reduce-only flatten; **không** được chỉ alert rồi tiếp tục.  
9. Chỉ account có pagination hoàn tất, dữ liệu fresh, không unresolved break và protection hợp lệ mới thành `READY`; còn lại giữ locked.  
10. Gửi `Recovery OK` hoặc SEV1 chi tiết qua outbox.

### 11.3 Continuous reconciliation

Khi có open order/position, recon theo interval được certification quy định và ngay sau reconnect, cancel/flatten, sleep/resume hoặc clock jump. Ingest execution cursor luôn có overlap + dedup để không mất fill tại ranh giới thời gian.

Mọi drill/fault acceptance nằm ở mục 18; một lần kill-process thủ công không đủ chứng minh recovery.

---

## 12. Backtest & AI (sau MVP)

### 12.1 Backtest/replay — D3

- Dùng cùng strategy/feature logic với PAPER/LIVE qua injected clock/data/execution ports.
- Không look-ahead: chỉ dữ liệu có thể biết tại event time; ghi data version, timezone, fee/slippage/fill assumptions.
- OHLC không đủ suy ra thứ tự stop/limit trong cùng candle hoặc partial fill; trường hợp mơ hồ dùng policy bảo thủ và ghi rõ.
- Cùng dataset/config/seed phải cho cùng kết quả.

### 12.2 AI shadow — D4

Target dự kiến: `P(lợi nhuận(H) > ngưỡng sau phí)` đã hiệu chỉnh, nhưng horizon/label/baseline/sample gate phải được chốt trong spec AI riêng.

- Dataset/feature/model version immutable và truy vết; walk-forward/out-of-sample, purge/embargo, calibration và post-cost metric bắt buộc.
- Training chạy process riêng và không tranh CPU/RAM/I/O với trading core.
- Chỉ shadow DEMO trước; Owner promote thủ công. Không auto-promote LIVE.
- Rollback chỉ tự động khi metric, sample size và observation delay đã định nghĩa; rollback drill phải pass.

---

## 13. Cấu trúc thư mục đề xuất (chưa tạo code)

```
APP_Trade_Tu_Dong_Tu_Hoc/
├── Kien-truc-App-Desktop-Solo-v1.3.md        # nguồn sự thật
├── AGENTS.md                                 # nguyên tắc triển khai từ v1.3
├── docs/
│   ├── mvp-capability-matrix.md              # requirement → test → evidence
│   └── decisions/                            # ADR phát sinh sau v1.3
├── src/
│   └── autotrade/                            # Python package
│       ├── entrypoints/                      # gui / headless, loại trừ nhau
│       ├── app_ui/                           # chỉ PySide6 D1c
│       ├── core/
│       │   ├── domain/                       # Decimal models, IDs, clock
│       │   ├── adapters/                     # interface + paper + ccxt D1
│       │   ├── market/
│       │   ├── features/
│       │   ├── strategy/
│       │   ├── risk/
│       │   ├── oms/
│       │   ├── ledger/
│       │   └── notify/                       # telegram + toast
│       └── persistence/                      # sqlite models
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   ├── fault/
│   └── packaged/
└── data/                                     # dev only, gitignore
```

Không tạo sẵn `ai/`, `backtest/`, `plugins/` hay `api/` trong D1. Phase nào bắt đầu mới tạo module của phase đó.

---

## 14. Lộ trình (mục tiêu trước code)

| Giai đoạn | Mục tiêu | Exit (đo được) |
|---|---|---|
| **D0 — Khoá tài liệu** *(đang ở đây)* | Duyệt v1.3, điền mục 16, hoàn thiện constitution/AGENTS + capability matrix | Mục 20 được ký; không còn quyết định kiến trúc D1 mơ hồ |
| **D1a — Deterministic core/Paper** | Domain + SQLite journal/outbox + fake/Paper + Risk/OMS/KS/Recovery + Telegram; chưa CCXT/UI | Unit/state/integration/fault suite mục 18 pass; crash scripted không tạo duplicate exposure |
| **D1b — Một CCXT DEMO** | Một exchange/market/account/symbol đã chọn; contract suite và real DEMO | ≥50 completed lifecycles, injected faults pass, continuous run ≥72h không unresolved recon |
| **D1c — Desktop MVP** | UI tối thiểu + installer + vận hành Windows | Clean Win11 x64 install; single-instance, sleep/resume, backup/restore/manual-upgrade pass; operational soak tổng ≥14 ngày |
| **D1.1 — LIVE-readiness riêng** | Chứng nhận đúng một tuple account/market/symbol; LIVE vẫn optional | Tất cả gate mục 06 + LIVE fault matrix pass; Owner ký riêng; attended-only |
| **D2 — Adapter thứ hai / multi-account** | MT5 hoặc CCXT thứ hai; process ownership và portfolio scope | Hai DEMO account không cross-state; cùng contract/fault suite pass |
| **D3 — Backtest/replay** | Engine deterministic, no-look-ahead | Repeatable results + documented data/fill assumptions |
| **D4 — AI shadow/retrain** | AI spec, model governance, process riêng | Walk-forward/calibration gate + manual promote/rollback drill |
| **D5+ — Mở rộng** | Chứng khoán, external plugin SDK, unattended core service/dead-man nếu thật sự cần | Gate riêng theo feature; vẫn không multi-user |

**Nguyên tắc:** duyệt D0 chỉ cho phép bắt đầu D1a; không đồng nghĩa duyệt LIVE. Backtest đứng trước AI. Số ngày soak là bằng chứng vận hành, không phải bằng chứng lợi nhuận.

---

## 15. Backlog tài liệu / chuẩn bị (trước code)

| ID | Việc | Trạng thái |
|---|---|---|
| D0-01 | Review và ký tiêu chí mục 20 cho file v1.3 | Chờ Owner |
| D0-02 | Điền các lựa chọn bắt buộc ở mục 16 | Chờ Owner |
| D0-03 | Chốt D1 runtime minor `3.14.x`; exact patch/dependency lock được xác nhận bằng compatibility smoke trước implementation trading | Chờ D1a-00 |
| D0-04 | Hoàn thiện constitution + viết `AGENTS.md` trỏ v1.3 | Trước D1 |
| D0-05 | Viết `docs/mvp-capability-matrix.md`: mỗi G/ADR → test → phase → evidence | Trước D1 |
| D0-06 | Review ToS sàn dự định dùng bot | Owner |
| D0-07 | Xác nhận Windows 11 baseline hoặc Windows 10 22H2 có ESU | Owner |
| D0-08 | Xác nhận mặc định kỹ thuật mục 07, backup 7 bản, log 30 ngày | Chờ Owner (có thể chấp nhận mặc định) |

Backlog code chỉ được sinh sau khi D0-01, D0-02 và D0-04 đến D0-08 hoàn tất. LIVE tasks không được trộn vào D1a–D1c.

---

## 16. Thông số cá nhân Owner (điền trước D1)

> Không ghi API key, password, PIN, Bot Token, Chat ID/User ID thật vào file/repo. Các giá trị secret/identifier được nhập trong app khi phase tương ứng chạy.

| Hạng mục | Bắt buộc? | Giá trị Owner điền |
|---|---|---|
| CCXT exchange + market + sandbox endpoint D1b (vd. Binance spot testnet) | Có | _…_ |
| Symbol + timeframe rule strategy đầu tiên | Có | _…_ |
| Chấp nhận guardrail mặc định mục 07 hay ghi bộ limit khác | Có | _…_ |
| Máy mục tiêu: Windows 11 x64 hay Windows 10 22H2 + ESU | Có | _…_ |
| Chấp nhận runtime D1 candidate Python 3.14.x | Có | _…_ |
| Telegram private bot/chat sẽ cấu hình trong app | Có trước exit D1a | Tạo bot khi vào D1; không ghi ID/token ở đây |
| MT5 | Không trong D1 | Mặc định xem xét ở D2 |
| Ngôn ngữ UI | Không (mặc định Tiếng Việt) | Tiếng Việt |

Nếu các mục bắt buộc còn trống thì chưa mở D1. Việc chọn exchange/symbol không đồng nghĩa cho phép LIVE.

---

## 17. Rủi ro sản phẩm (solo + đa sàn)

| ID | Rủi ro | Giảm thiểu |
|---|---|---|
| P-01 | Hiểu nhầm CCXT = mọi sàn đã đủ chức năng trading | Certification theo tuple; D1 đúng một allowlist |
| P-02 | Precision/contract/hedge/stop/client-ID khác nhau | Instrument spec + runtime capability + contract/fault suite |
| P-03 | Nhầm PAPER/DEMO/LIVE hoặc endpoint | Account/credential tách; text/icon/màu; mode mismatch fail-closed |
| P-04 | Sleep, network change, Windows restart | Best-effort prevent sleep; resume/startup recovery; stop phía broker |
| P-05 | Crash sau broker accept gây submit trùng | Durable intent + deterministic client ID + lookup; UNKNOWN không retry mù |
| P-06 | Stop reject/mất/không khớp do gap/halt | Không override LIVE; continuous protection recon; reduce-only flatten; capital cap |
| P-07 | Disk full, DB corruption hoặc migration fail | WAL/FULL, atomic journal, SAFE_LOCK, pre-migration backup + restore drill |
| P-08 | ToS/API/bot hoặc market-data license không cho phép | Review trước allowlist; không dùng exchange chưa duyệt |
| P-09 | Telegram token/chat bị lộ hoặc command replay/stale | keyring, private chat+user, update ID dedup, TTL; chỉ remote Pause |
| P-10 | Cùng Windows account bị chiếm; PIN bị bypass | Ghi rõ threat boundary; OS patch, BitLocker, key trade-only/no-withdraw/IP allowlist |
| P-11 | CCXT/broker/dependency update đổi semantics | Pin lockfile; certification invalidation; contract + packaged regression |
| P-12 | MT5 terminal/API không hỗ trợ giả định session/multi-account | Để D2; serialized ownership; calendar/bridge riêng |
| P-13 | Overfit/data leakage/model rollback sai | Backtest trước AI; walk-forward/purge/calibration; manual promotion |
| P-14 | LIVE không giám sát nhưng app/máy không có heartbeat độc lập | Baseline attended-only; core service/dead-man là feature/gate riêng |

---

## 18. Test strategy & release gates

### 18.1 Tầng kiểm thử

| Tầng | Phạm vi | Bắt buộc |
|---|---|---|
| Unit/state | Decimal risk math, rounding, FSM transitions, KS scope, clock/freshness | D1a |
| Property/scenario | Không state regression, fill không vượt quantity hợp lệ, reduce-only không flip | D1a |
| Contract adapter | Precision, place/query/cancel, direct/partial/late fill, pagination, fee/margin, protection | Mỗi adapter/exchange/market |
| Integration | Strategy → Risk reservation → journal → OMS → fake adapter → fill/ledger/outbox | D1a |
| Fault/crash | Kill process và lỗi dependency tại mọi biên side effect | D1a; mở rộng trước LIVE |
| E2E DEMO | Broker thật đã allowlist + Telegram + recovery | D1b |
| Packaged Windows | Installer, single-instance, sleep/resume, backup/restore/upgrade | D1c |
| Soak | Continuous run + recon/outbox health | D1b/D1c |

### 18.2 Fault matrix tối thiểu

| Scenario | Kỳ vọng pass |
|---|---|
| Crash trước transaction intent commit | Không request ra broker, không reservation rác |
| Crash sau commit nhưng trước/đúng lúc send | Recovery phân biệt `NOT_SENT`/uncertain theo durable delivery state; uncertain phải query, không retry mù |
| Broker accept nhưng response timeout | `UNKNOWN`, giữ reservation, lookup/recon về đúng order, không duplicate exposure |
| Partial fill trong lúc tạo/cập nhật stop | Protection quantity theo fill; thất bại → L3 flatten + locked |
| Cancel timeout + late fill | `CANCEL_UNKNOWN`; ingest fill một lần; Risk/KS cập nhật đúng |
| Duplicate/out-of-order execution/status | Unique fill; state không đi lùi; ledger hội tụ |
| Rate-limit/network/auth disconnect | Entry dừng; emergency/recon lane ưu tiên; không vòng retry vô hạn |
| Quote/account/instrument/calendar stale | Không tăng exposure; UI/Telegram nêu đúng dữ liệu stale |
| Disk full/DB busy/corrupt/migration fail | `SAFE_LOCK`; không submit mới; restore path kiểm thử được |
| Persisted L2/L3/L4 rồi restart | KS không tự hạ; recovery chạy trước READY |
| Telegram outage/429/permanent 4xx | Outbox retry/dead-letter đúng; không mất event nguồn trong SQLite |
| Sleep/resume hoặc wall-clock jump | Quote/account/clock refresh + recovery subset trước trade |
| Manual/broker-orphan order hoặc position | Recon phát hiện, audit provenance, L2; không overwrite lịch sử |

### 18.3 Bất biến pass/fail

1. Không tăng exposure nếu thiếu risk-check + reservation đã commit.  
2. Không tự tạo duplicate exposure trong mọi fault scenario đã chứng nhận.  
3. Fill nhận lại nhiều lần chỉ có một hiệu lực.  
4. Restart không làm hạ KS hoặc giải phóng reservation chưa được recon.  
5. Account không vào `READY` khi recovery/pagination/capability/freshness chưa hoàn tất.  
6. LIVE không tồn tại exposure thiếu broker-side protection; phát hiện thiếu phải flatten/lock, không chỉ alert.  
7. Broker exposure và SQLite derived state cuối cùng hội tụ; lịch sử intent/audit không bị xoá/sửa mù.  
8. Không secret/PIN/token xuất hiện trong DB thường, config, JSONL, UI error hoặc test artifact.

Mỗi gate lưu evidence: app/dependency versions, environment, seed/config, test report, broker account/mode masked, start/end time và unresolved incidents. Không có evidence = chưa pass.

---

## 19. Quan hệ với Enterprise blueprint

| Chủ đề Enterprise | Desktop Solo v1.3 |
|---|---|
| FSM, Risk, Recovery, test gate | Quy tắc trong **file này** là đầy đủ và ưu tiên; không kế thừa ngầm |
| Kafka, K8s, Vault, dual-control, SaaS | Bỏ |
| MetaApi mặc định | Không; MT5 official chỉ xem xét D2 |
| Adapter | Một built-in Paper + một CCXT DEMO trước; external plugin D5+ |
| JWT/login/RBAC | Không |
| AI 9 bước | Chỉ tham khảo khi viết spec AI D4; không thuộc D1 |

Enterprise blueprint có thể cung cấp ý tưởng nhưng không phải dependency để hiểu, triển khai hoặc nghiệm thu Desktop Solo.

---

## 20. Tiêu chí duyệt D0 (Owner ký)

Đánh dấu khi đồng ý. Chữ ký D0 chỉ cho phép bắt đầu **D1a PAPER**, không cho phép LIVE:

- [ ] Đồng ý tầm nhìn mục 00 và mục tiêu G1–G7.  
- [ ] Đồng ý D1 chỉ một account active, một CCXT DEMO exchange/market/symbol; MT5/multi-account để D2.  
- [ ] Đồng ý adapter D1 là built-in; external plugin, local HTTP API, AI và Backtest UI không thuộc MVP.  
- [ ] Đồng ý một CPython minor được pin, PySide6 + pyqtgraph, SQLite, python-telegram-bot và PyInstaller `onedir`.  
- [ ] Đồng ý one-process GUI/headless loại trừ nhau; baseline không có unattended LIVE.  
- [ ] Đồng ý PAPER/DEMO trước; 14 ngày là operational soak, không phải chứng minh lợi nhuận.  
- [ ] Đồng ý LIVE hard-disable tới gate riêng; stop broker-side không override và LIVE eligibility là machine-derived.  
- [ ] Đồng ý OMS durable intent/UNKNOWN không retry mù, recovery/recon và fault matrix mục 11/18.  
- [ ] Đồng ý Pause/Flatten local không bị PIN chặn; Telegram chỉ `/status`, `/pnl`, `/pause`.  
- [ ] Đồng ý nguồn sự thật theo domain: broker cho exposure hiện tại, SQLite cho app intent/FSM/audit/outbox, JSONL chỉ chẩn đoán.  
- [ ] Đã điền toàn bộ mục bắt buộc ở mục 16 mà không ghi secret vào repo.  
- [ ] Sẽ hoàn thiện constitution, `AGENTS.md` và `docs/mvp-capability-matrix.md` trước khi code.  
- [ ] Hiểu đây không phải lời khuyên đầu tư; mọi quyết định LIVE cần phê duyệt riêng và do Owner chịu trách nhiệm.

**Chữ ký Owner / ngày:** __________________

---

*Không phải lời khuyên đầu tư, tài chính hay pháp lý. Ứng dụng phục vụ tự doanh vốn riêng.*
