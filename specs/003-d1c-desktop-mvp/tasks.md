---
description: "Task list for D1c Desktop MVP (PySide6 + installer)"
---

# Tasks: D1c Desktop MVP

**Input**: [plan.md](./plan.md), [spec.md](./spec.md), [data-model.md](./data-model.md), [research.md](./research.md), [contracts/](./contracts/), [WORKPLAN-NOW.md](./WORKPLAN-NOW.md)

**Phase guard**: D1c only — PySide6 UI + PyInstaller ops. No LIVE, no multi-exchange, no AI/Backtest UI, no FastAPI. UI MUST NOT bypass Risk/OMS/cert gates.

**Clarify locked** (2026-07-23): Pause without PIN; Telegram optional at first-run; one-folder installer — see [research.md](./research.md).

**Implement gate (hard)**:
- Docs/stub tasks (T001–T010) MAY proceed while D1b soak runs.
- UI trading E2E / Enable DEMO from UI / packaged DEMO (T020+) **WAIT** until D1b `certification_records.valid=true` after V8 ≥72h.

## Format: `[ID] [P?] [Story?] Description`

---

## Phase 0: Docs complete (this PR)

- [x] T000 Lock clarify Q1–Q3 in research.md + WORKPLAN-NOW.md
- [x] T000a Write data-model.md + contracts (ui-core-boundary, packaged-ops, screens)
- [x] T000b Write this tasks.md + update checklist

---

## Phase 1: Setup — UI extra + skeleton (safe during soak)

**Independent Test**: `import autotrade` without PySide6 still works; `pytest -m "d1a or d1b"` green

- [x] T001 Add optional-dependencies `ui = ["PySide6>=6.7,<7"]` in `pyproject.toml` (do not put PySide6 in main deps)
- [x] T002 [P] Add pytest marker `d1c` in `pyproject.toml` + `tests/conftest.py`
- [x] T003 [P] Create `src/autotrade/app_ui/` package with `__init__.py` docstring “D1c only; no trading mutations here”
- [x] T004 [P] Add `src/autotrade/entrypoints/desktop.py` stub that refuses to start if ui extra missing (clear error)
- [x] T005 [P] Unit test: `core`/`oms`/`risk`/`strategy` modules do not import PySide6 (`tests/unit/test_ui_import_boundaries.py`)
- [x] T006 Update `AGENTS.md` phase D1c row pointer to `specs/003-d1c-desktop-mvp/`

**Checkpoint**: Stub merges without requiring Qt installed in default CI

---

## Phase 2: Foundational UI shell (after T001–T006; still no DEMO E2E gate)

- [x] T010 Implement MainWindow + navigation shell (empty pages) in `app_ui/`
- [x] T011 [P] Tray stub: show/hide main; Quit; Pause hook wired to KillSwitch API (unit with fake KS)
- [x] T012 Single-instance guard helper (QLocalServer or win mutex) + unit test on Windows
- [x] T013 [P] Read-only DashboardSnapshot builder from existing UoW (no Qt) in `app_ui/services/` or `core` projection module
- [x] T014 Wire desktop entrypoint to show MainWindow when `[ui]` installed

**Checkpoint**: App opens empty shell on Owner machine with `pip install .[ui]` — **PASSED**
(PySide6 6.11.1 / Python 3.14, shell + tray render, `autotrade-desktop --check` exit 0).

**Layering locked in Phase 2** (enforced by `tests/unit/test_ui_import_boundaries.py`):

| Layer | Qt? | Contents |
|---|---|---|
| `app_ui/services/` | never | `dashboard` read models, `screens` registry, `single_instance` |
| `app_ui/controllers/` | never | `tray.TrayController` (Pause, snapshot, tooltip) |
| `app_ui/views/` | yes, eager | `main_window.MainWindow`, `tray.AppTray` |
| `entrypoints/desktop.py` | yes, **lazy only** | must stay importable without the extra |

Exit codes: `0` ok · `2` missing `[ui]` extra · `3` another instance
(mutex `AutoTradeAI.Solo`).

**Fail-closed rules the read model now enforces itself** (QA cycle 2 found both
fail-OPEN; regression tests in `tests/unit/test_dashboard_snapshot.py`):

- `ActiveAccountView` uses an **allowlist** (`TRADABLE_MODES = {PAPER, DEMO}`).
  LIVE — or any future/typo'd mode — is never `is_ready`, even with a valid
  cert, and the banner appends `— MODE NOT PERMITTED`.
- `is_trading_blocked` includes `not account.is_ready`, so a DEMO account with
  a missing/revoked cert reads as blocked.
- `build_live_monitor_page` **always returns every in-flight intent**; `limit`
  caps only the settled padding, and `truncated` reports what was left out.
  Silent truncation is forbidden — UNKNOWN must never be paged away.

### Deferred — need an Owner decision, NOT silently patched

- [x] T015 `autotrade-headless` takes no single-instance lock, so the
      `AutoTradeAI.Solo` mutex only excludes a second **desktop**, not
      desktop + headless together. Decide whether the "one trading process"
      invariant (v1.4) should be enforced by a shared lock, and which process
      wins. Changing this touches D1a/D1b runtime semantics.
- [ ] T016 `kill_switch_state` has no unique constraint on `scope`, while
      `KillSwitch.load/persist` use `.one_or_none()`. Duplicate rows would make
      tray **Pause** raise `MultipleResultsFound` — the one action that must
      never fail. Needs a migration + ADR note, not a UI-side try/except.
- [ ] T017 `order_intents` has no timestamp column and `intent_id` is a random
      UUID, so the Live Monitor cannot order "most recent first". T041 needs a
      time column (or an ordered surrogate key) before it can page usefully.

---

## Phase 3: User stories (WAIT: D1b valid=true for DEMO paths)

### US1 — Install & launch [P1]

- [x] T020 PyInstaller one-folder spec + build script under `packaging/`
- [x] T021 [P] Packaged smoke: launch + single-instance (`tests/packaged/`)
- [x] T022 Clean-machine checklist doc in quickstart.md

### US2 — Broker Hub [P1] (cert gate)

- [x] T030 Broker Hub views: Paper/DEMO, Test connection, capability redacted
- [x] T031 Enable DEMO calls same assert as headless; refuse if invalid cert
- [x] T032 Switch account UI fail-closed (flat/recon/UNKNOWN)
- [x] T033 Integration tests marker `d1c` with Fake adapter (no REAL required)

### US3 — KS + Live Monitor [P2]

- [x] T040 KS panel L1–L4 + Pause without PIN
- [x] T041 Live Monitor table includes UNKNOWN; no blind-retry button
- [x] T042 Flatten confirm dialog → core flatten path

### US4 — Strategy / History / Settings [P3]

- [x] T050 Strategy view read-only hard ceilings
- [x] T051 History filter + CSV export redacted
- [x] T052 Settings: PIN change, optional Telegram, allowlist read-only, backup trigger
- [x] T053 Autostart option (Windows) documented

---

## Phase 4: Ops soak D1c (≥14d) — after MVP UI

- [x] T060 Operational soak runbook (≥14d) separate from D1b 72h — `specs/003-d1c-desktop-mvp/OWNER-D1C-OPS-SOAK.md`
- [x] T061 Fill matrix G6 / ADR-D13 packaged Evidence — the ≥14d wall-clock window itself is still an Owner action pending against a real machine, tracked in the runbook above, not by this checkbox

---

## Parallel notes

- T001–T006 are the only code tasks intended **during** D1b V8 soak.
- Do not start second `run-soak` on Owner machine.
