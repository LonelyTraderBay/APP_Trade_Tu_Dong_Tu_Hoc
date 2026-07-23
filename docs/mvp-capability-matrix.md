# MVP Capability Matrix — AutoTrade Desktop Solo

**Nguồn quy phạm:** `Kien-truc-App-Desktop-Solo-v1.4.md`  
**Mục đích:** mỗi yêu cầu → phase → loại test → evidence khi exit.  
**Trạng thái:** D0 reviewed 2026-07-23 — Owner chấp nhận mặc định; exchange/symbol TBD tới D1b. Cột Evidence để trống đến khi phase chạy.

---

## Cách dùng

| Cột | Ý nghĩa |
|---|---|
| ID | G/ADR/mục trong v1.4 |
| Phase | Phase sớm nhất phải đạt |
| Test | Suite tối thiểu (mục 18) |
| Evidence | Artifact khi pass (điền sau) |

Không có evidence = chưa pass gate.

---

## G1 — Đa sàn / adapter

| ID | Yêu cầu (rút) | Phase | Test | Evidence |
|---|---|---|---|---|
| G1.1 | Broker Adapter Interface; không hard-code sàn trong Strategy/Risk/OMS | D1a/D1b | contract adapter; review import boundaries | |
| G1.2 | Wizard tự kết nối | D1c | E2E UI Paper + DEMO | |
| G1.3 | Chỉ tuple đã chứng nhận | D1b | allowlist negative test | |
| G1.4 | Chuẩn hoá symbol/margin/exposure | D1a | unit instrument + risk projection | |
| G1.5 | Một account active D1 | D1a | integration single-account lock | |

## G2 — Mode

| ID | Yêu cầu (rút) | Phase | Test | Evidence |
|---|---|---|---|---|
| G2.1–G2.3 | PAPER/DEMO/LIVE tách; Paper deterministic | D1a | property + Paper seed replay | |
| G2.4–G2.5 | LIVE hard-disable tới gate | D1a/D1.1 | UI/state cannot enable LIVE in D1 | |

## G3 — An toàn vốn / OMS / Recovery

| ID | Yêu cầu (rút) | Phase | Test | Evidence |
|---|---|---|---|---|
| G3.1 | Tăng exposure qua Risk + reservation | D1a | integration + unit Decimal | |
| G3.2 | L1–L4; Telegram chỉ Pause | D1a | KS scope tests; Telegram command suite | |
| G3.3 | Durable intent; UNKNOWN không retry mù | D1a | fault matrix crash/timeout | |
| G3.4 | Recon; broker sự thật hiện tại | D1a | recon orphan/missing fill | |
| G3.5 | Stop native LIVE bắt buộc | D1.1 | LIVE fault protection | |
| G3.6–G3.7 | Startup Recovery; eligibility machine | D1a/D1.1 | recovery scripted + eligibility unit | |

## G4 — Strategy / AI

| ID | Yêu cầu (rút) | Phase | Test | Evidence |
|---|---|---|---|---|
| G4.1 | Rule strategy + 1 symbol/TF | D1a | deterministic signal tests `rule_sma_cross_v1` | |
| G4.2–G4.3 | AI sau Backtest; retrain sidecar; promote thủ công | D4 | walk-forward + promote drill | |
| G4.4 | AI Module Interface + contract | D4 | AI contract suite §12.3.3 | |
| G4.5 | Learning Store + namespaces | D4 | lineage + namespace retrieve tests | |
| §07.3 | Strategy mặc định SMA cross | D1a | unit SMA/ATR/cooldown/abstain | |
| §07.4 | Feature schema versioned | D1a | snapshot version + no look-ahead | |

## G5 — Telegram

| ID | Yêu cầu (rút) | Phase | Test | Evidence |
|---|---|---|---|---|
| G5.1–G5.5 | Config test; push events; digest ngày; `/status|/pnl|/pause`; mode trên tin | D1a | outbox retry/dedup; reject wrong chat; redaction | |

## G6 — Desktop

| ID | Yêu cầu (rút) | Phase | Test | Evidence |
|---|---|---|---|---|
| G6.1–G6.4 | No login; PIN gates; tray Pause; single-instance | D1c | packaged single-instance; PIN lockout | |

## ADR stack

| ID | Yêu cầu (rút) | Phase | Test | Evidence |
|---|---|---|---|---|
| ADR-D01 | Pin one CPython minor (+ fallback) | D1a-00 | smoke Win clean + lockfile | |
| ADR-D03 / D03.1 | SQLite WAL + bảng trading tối thiểu | D1a | migration + atomic intent txn | |
| ADR-D04 | Outbox durable; queue wake-only | D1a | restart replay outbox | |
| ADR-D06 | keyring only | D1a | no secret in sqlite/log fixtures | |
| ADR-D09 | Built-in adapters D1 | D1b | certification record tuple | |
| ADR-D11 | PIN Argon2id + lockout | D1a | unit PIN + audit | |
| ADR-D12 | Monotonic timeouts; clock skew | D1a | clock fault tests | |
| ADR-D13 | One process; no HTTP | D1c | packaged assert no listen port | |
| ADR-D14 | LIVE eligibility key | D1.1 | eligibility invalidation tests | |

## Fault matrix (mục 18.2) — D1a tối thiểu

Mỗi hàng fault D1 (không gồm hàng D4) phải có evidence trước exit D1a/D1b tương ứng. Hàng D4 chỉ khi vào D4.

| Scenario group | Phase |
|---|---|
| Crash/commit/send/UNKNOWN/partial/cancel/late fill/dup | D1a |
| Rate-limit/disconnect/stale/disk/KS restart/Telegram/sleep/orphan | D1a–D1c |
| AI sidecar / schema hash / namespace / promote PIN | D4 |

## Phase exit checklist (tóm tắt)

| Phase | Exit đo được (v1.4 §14) | Matrix rows phải xanh |
|---|---|---|
| D0 | Mục 20 ký; mục 16 mặc định OK; exchange TBD | D0-01…05, 07…10 |
| D1a | Fault + Paper FSM (symbol nội bộ) | G3, G4.1, G5, ADR-D03.1, fault D1 |
| D1b | Sau D0-11 (chốt sàn) + DEMO lifecycle + soak ≥72h | G1, ADR-D09, E2E DEMO |
| D1c | Installer + UI MVP + soak ≥14d ops | G6, G7 UX, packaged |
| D3 | Repeatable backtest; freeze feature/label | §07.4, §12.1 |
| D4 | AI contract + Learning Store + promote drill | G4.2–G4.5, §12.3–12.4 |

---

## Owner sign-off (D0)

- [x] Đã đọc matrix này và khớp v1.4  
- [x] Đồng ý không đánh dấu pass khi thiếu Evidence  
- [x] Đồng ý D4 rows không thuộc MVP  
- [x] Đồng ý exchange/symbol TBD không mở D1b/LIVE  

**Chữ ký / ngày:** Owner (C-PC) / 2026-07-23
