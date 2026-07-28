# MVP Capability Matrix — AutoTrade Desktop Solo

**Nguồn quy phạm:** `Kien-truc-App-Desktop-Solo-v1.4.md`  
**Mục đích:** mỗi yêu cầu → phase → loại test → evidence khi exit.  
**Trạng thái:** D0 reviewed 2026-07-23 — mặc định OK; **D0-11 chốt** 2026-07-23 (`binance` spot Binance Spot Testnet / `BTC/USDT` / `15m`). Cột Evidence để trống đến khi phase chạy.

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
| G1.1 | Broker Adapter Interface; không hard-code sàn trong Strategy/Risk/OMS | D1a/D1b | contract adapter; review import boundaries | 2026-07-23 mock + REAL V7/V8: `BrokerAdapter` protocol; OMS/Risk/Strategy không import `ccxt`; Spot exposure via balance (hotfix #8). Lifecycle=`52`; soak=`soak_cb50ba457b9d9a1b` ≥72h passed; `cert.valid=true`; DEMO enabled `demo-binance` |
| G1.2 | Wizard tự kết nối | D1c | E2E UI Paper + DEMO | |
| G1.3 | Chỉ tuple đã chứng nhận | D1b | allowlist negative test | 2026-07-23 `pytest -m d1b` — `test_allowlist_*`, `test_phase_boundary_d1b` PASS (`binance`/spot/testnet/`BTC/USDT`/`15m`). 2026-07-28 hardening: `CcxtDemoAdapter.cancel_order` was the one exchange-touching method missing an `assert_allowlisted(...)` gate (every other method — `connect`/`place_order`/`fetch_ohlcv_closed`/`upsert_protection` — already had it); added, covered by `tests/contract/test_allowlist_tuple.py::test_cancel_order_refused_when_not_allowlisted`. |
| G1.4 | Chuẩn hoá symbol/margin/exposure | D1a | unit instrument + risk projection | 2026-07-28 raw-reference sub-yêu-cầu ("Lưu ... raw reference") vá xong: migration `0004_raw_broker_reference` thêm `orders.raw_reference` (JSON, nullable); `DurableSubmitter._finalize_fill`/`cancel_intent._persist_terminal` ghi `redact_mapping(order)` full adapter response (Paper + CcxtDemoAdapter, kể cả `raw` ccxt payload lồng bên trong) trước khi mất đi. `pytest -m "d1a or d1b"` PASS incl. `test_orders_raw_reference_column`, `test_durable_submit_paper_fill`, `test_durable_submit_demo_before_send`. Phần còn lại của G1.4 (chuẩn hoá venue/market/currency/contract/position-mode/leg/ticket + risk exposure projection đầy đủ) chưa có evidence riêng — vẫn PARTIAL. |
| G1.5 | Một account active D1 | D1a | integration single-account lock | 2026-07-28 verified: `switch_active_account` (`src/autotrade/core/accounts/active.py`) unconditionally sets every `Account.is_active=False` before flipping the target to `True`, so exactly one account is ever active; `tests/integration/test_account_switch.py::test_switch_paper_demo_when_flat` asserts both flags post-switch and `::test_switch_refused_when_not_flat`/`::test_switch_refused_open_recon`/`::test_switch_refused_unknown_intent` cover the fail-closed refusal paths (not-flat, open recon, UNKNOWN/SUBMITTING intent). Note (post-audit finding, kept visible): this enforcement code and its test suite were authored as part of D1b's Paper↔DEMO account-switching work — all four tests carry `@pytest.mark.d1b`, not `d1a` — rather than as standalone D1a work, even though the capability satisfies the D1a-phase G1.5 requirement. |

## G2 — Mode

| ID | Yêu cầu (rút) | Phase | Test | Evidence |
|---|---|---|---|---|
| G2.1–G2.3 | PAPER/DEMO/LIVE tách; Paper deterministic | D1a | property + Paper seed replay | 2026-07-23 `pytest -m d1a` — `test_paper_replay_seed`, durable submit PASS |
| G2.4–G2.5 | LIVE hard-disable tới gate | D1a/D1.1 | UI/state cannot enable LIVE in D1 | 2026-07-23 `test_phase_boundary_d1a` — PAPER-only manifest; no LIVE mode |

## G3 — An toàn vốn / OMS / Recovery

| ID | Yêu cầu (rút) | Phase | Test | Evidence |
|---|---|---|---|---|
| G3.1 | Tăng exposure qua Risk + reservation | D1a | integration + unit Decimal | 2026-07-23 `test_risk_and_ks`, `test_durable_submit_paper_fill` |
| G3.2 | L1–L4; Telegram chỉ Pause | D1a | KS scope tests; Telegram command suite | 2026-07-23 `test_ks_persist_restart`, `test_telegram_commands` (/pause→L1) |
| G3.3 | Durable intent; UNKNOWN không retry mù | D1a | fault matrix crash/timeout | 2026-07-23 crash/commit/timeout UNKNOWN tests PASS |
| G3.4 | Recon; broker sự thật hiện tại | D1a | recon orphan/missing fill | 2026-07-23 `test_recon_orphans` |
| G3.5 | Stop native LIVE bắt buộc | D1.1 | LIVE fault protection | |
| G3.6–G3.7 | Startup Recovery; eligibility machine | D1a/D1.1 | recovery scripted + eligibility unit | 2026-07-23 `test_startup_recovery_*` (D1a Paper) |

## G4 — Strategy / AI

| ID | Yêu cầu (rút) | Phase | Test | Evidence |
|---|---|---|---|---|
| G4.1 | Rule strategy + 1 symbol/TF | D1a | deterministic signal tests `rule_sma_cross_v1` | 2026-07-23 `test_rule_sma_cross_v1`, `test_paper_signal_replay`. **2026-07-28**: Paper now has a REAL (not just tested-in-isolation) signal→submit path — `core/oms/trading_loop.py::run_trading_loop_iteration` fetches real closed OHLCV (`CcxtDemoAdapter.fetch_ohlcv_closed`, read-only market data), persists candles/features, evaluates `rule_sma_cross_v1`, and submits through the real risk-gated `DurableSubmitter` against `PaperAdapter` on `ENTER_LONG`/`EXIT_LONG` — see `tests/integration/test_trading_loop.py` and `specs/001-d1a-paper-core/tasks.md` T076. **2026-07-28 (later same day)**: the loop is now runnable end-to-end as a real Owner-operated process, not just library code — `autotrade-headless run-trading-loop` (`src/autotrade/entrypoints/headless.py`) polls it every 60s, forever, until Ctrl+C, refuses to start on a non-PAPER active account or a locked Startup-Recovery check, and holds the SAME `rule`/`market_adapter`/`exec_adapter` instances across every poll. See `specs/001-d1a-paper-core/tasks.md`'s "T076 follow-up" entry and `tests/unit/test_headless_entrypoint.py`. |
| G4.2–G4.3 | AI sau Backtest; retrain sidecar; promote thủ công | D4 | walk-forward + promote drill | |
| G4.4 | AI Module Interface + contract | D4 | AI contract suite §12.3.3 | |
| G4.5 | Learning Store + namespaces | D4 | lineage + namespace retrieve tests | |
| §07.3 | Strategy mặc định SMA cross | D1a | unit SMA/ATR/cooldown/abstain | |
| §07.4 | Feature schema versioned | D1a | snapshot version + no look-ahead | |

## G5 — Telegram

| ID | Yêu cầu (rút) | Phase | Test | Evidence |
|---|---|---|---|---|
| G5.1–G5.5 | Config test; push events; digest ngày; `/status|/pnl|/pause`; mode trên tin | D1a | outbox retry/dedup; reject wrong chat; redaction | 2026-07-23 telegram commands/digest/outbox/redaction tests PASS |

## G6 — Desktop

| ID | Yêu cầu (rút) | Phase | Test | Evidence |
|---|---|---|---|---|
| G6.1–G6.4 | No login; PIN gates; tray Pause; single-instance | D1c | packaged single-instance; PIN lockout | 2026-07-27 no login screen by design (`MainWindow` opens directly, no auth gate); PIN Argon2id set/verify/lockout via `tests/unit/test_settings_controller.py`; tray + KS-panel Pause never PIN-gated (`tests/integration/test_kill_switch_ui.py::test_pause_button_has_no_pin_field_and_no_confirmation_dialog`); single-instance shared across desktop+headless (`tests/unit/test_single_instance.py`, `tests/unit/test_headless_entrypoint.py`) and packaged EXE (`tests/packaged/test_packaged_launch.py::test_second_instance_is_refused_while_first_holds_the_lock`, real PyInstaller build). Ops soak ≥14d runbook: `specs/003-d1c-desktop-mvp/OWNER-D1C-OPS-SOAK.md` (T060) — wall-clock window not yet run, tracked separately from this table row. |

## ADR stack

| ID | Yêu cầu (rút) | Phase | Test | Evidence |
|---|---|---|---|---|
| ADR-D01 | Pin one CPython minor (+ fallback) | D1a-00 | smoke Win clean + lockfile | 2026-07-23 branch `001-d1a-paper-core`: CPython **3.14.4**; `uv.lock` SHA256 `A9AA587170281CDB7A7206E5D4B8FBF6E36A99B065478A786A793E1F2D3F53E5`; deps allowlist only (no CCXT/PySide6/ML); `ruff check` PASS; `pytest --collect-only` (0 tests); `autotrade-headless --version` → 0.1.0a0 |
| ADR-D03 / D03.1 | SQLite WAL + bảng trading tối thiểu | D1a | migration + atomic intent txn | 2026-07-23: Alembic `0001_adr_d03_1`; `tests/unit/test_schema_adr_d03_1.py` PASS — đủ bảng ADR-D03.1, không `ai_*` |
| ADR-D04 | Outbox durable; queue wake-only | D1a | restart replay outbox | 2026-07-23 `test_telegram_outbox_retry_and_dead_letter` |
| ADR-D06 | keyring only | D1a | no secret in sqlite/log fixtures | 2026-07-23 `test_secret_redaction_in_notify_payloads` |
| ADR-D09 | Built-in adapters D1 | D1b | certification record tuple | 2026-07-23 harness + **REAL V8 DONE** 2026-07-26: app=`0.1.0a0`; ccxt=`4.5.68`; tuple=`binance`/`spot`/`binance_spot_testnet`/`BTC/USDT`/`15m`; lifecycle=`52`; soak=`soak_cb50ba457b9d9a1b` start=`2026-07-23 07:53:35Z` end=`2026-07-26 16:42:09Z` passed; cert.valid=`true`; DEMO=`demo-binance` READY; DB=`%LOCALAPPDATA%/AutoTradeAI/autotrade.sqlite3`. Note: runner crashed at finalize (naive/aware datetime); orphan finalize after wall≥72h + recon=0 — fix `_as_utc` in `soak.py`. Hotfix Spot #8 retained. |
| ADR-D11 | PIN Argon2id + lockout | D1a | unit PIN + audit | 2026-07-23 `test_pin_verifier` |
| ADR-D12 | Monotonic timeouts; clock skew | D1a | clock fault tests | 2026-07-23 `test_clock_jump_recovery` |
| ADR-D13 | One process; no HTTP | D1c | packaged assert no listen port | 2026-07-23 headless stub + boundary; **2026-07-27 packaged E2E complete**: `packaging/autotrade-desktop.spec` one-folder build, `desktop.py`/`headless.py` never open a listening socket (grep-clean, no `socket.listen`/HTTP server anywhere in `entrypoints/`), real single-instance guard proven against the built `AutoTradeAI.exe` (`tests/packaged/test_packaged_launch.py`). |
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
| D0 | Mục 20 ký; mục 16 OK; **D0-11 xong** (`binance`/spot/testnet/`BTC/USDT`/`15m`) | D0-01…05, 07…11; D0-06 Owner ToS trước credential DEMO |
| D1a | Fault + Paper FSM (symbol nội bộ) | G3, G4.1, G5, ADR-D03.1, fault D1 |
| D1b | D0-11 + D1a merged + DEMO lifecycle ≥50 + soak ≥72h | G1, ADR-D09 — **EXIT 2026-07-26:** V7 lifecycle=`52`; V8 soak passed; `cert.valid=true`; `enable-demo` OK. Harness: `pytest -m "d1a or d1b"`. Runbook: `specs/002-d1b-ccxt-demo/OWNER-D1B-EXIT.md` |
| D1c | Installer + UI MVP + soak ≥14d ops | G6, G7 UX, packaged |
| D3 | Repeatable backtest; freeze feature/label | §07.4, §12.1 |
| D4 | AI contract + Learning Store + promote drill | G4.2–G4.5, §12.3–12.4 |

---

## Owner sign-off (D0)

- [x] Đã đọc matrix này và khớp v1.4  
- [x] Đồng ý không đánh dấu pass khi thiếu Evidence  
- [x] Đồng ý D4 rows không thuộc MVP  
- [x] Đồng ý exchange/symbol **đã chốt D0-11** chỉ mở D1b DEMO (không mở LIVE) sau merge D1a + certification  
- [x] **D0-06** — đã review/chấp nhận ToS Binance Spot Testnet / bot trước credential DEMO (2026-07-23)

**Chữ ký / ngày:** Owner (C-PC) / 2026-07-23 (D0); D0-11 amend 2026-07-23; D0-06 ToS 2026-07-23
