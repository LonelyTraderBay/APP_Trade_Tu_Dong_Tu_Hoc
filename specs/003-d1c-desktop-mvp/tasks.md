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

## Post-audit fixes

- [x] T070 **FR-004 gap**: `run_startup_recovery` (`core/oms/recovery.py`) was
      fully implemented and D1a-tested but was only ever called from tests and
      D1b's soak/lifecycle harnesses — never from `entrypoints/desktop.py`. The
      Owner could open MainWindow and reach Broker Hub / Kill-switch / Live
      Monitor after a crash, sleep/resume, or interrupted session without the
      kill-switch-restore / adapter-connectivity / pagination / data-freshness
      / recon checklist ever running. Fixed by adding
      `app_ui/services/startup.py::run_desktop_startup_recovery` (Qt-free,
      mirrors `BrokerHubController`/`KillSwitchController` adapter
      construction) and wiring it into `desktop.py::main()` — after the
      single-instance guard, before `_run_gui()` shows the window and before
      the `--check` banner prints, so both reflect POST-recovery state. A
      locked result is passed through to `_run_gui`, which appends the
      recovery reasons to the MainWindow status bar (no new modal — same
      non-interrupting treatment as any other SAFE_LOCK/blocked state).
      Tests: `tests/unit/test_startup_service.py`,
      `tests/unit/test_desktop_entrypoint.py`.

- [x] T071 **G1.2/G7 gap**: architecture's core product promise — "Owner tự
      kết nối trong app (wizard), không cần sửa code": chọn adapter → nhập
      credential → Test connection → lưu (secret vào keyring) → chọn
      Demo/Live — had no UI code path at all. The only way to store DEMO
      credentials was `autotrade-headless demo-store-creds --account-id
      demo-binance` (two `getpass.getpass()` prompts, terminal only); Broker
      Hub's Test/Enable buttons assumed a keyring entry already existed.
      Fixed by adding a credential-entry form to Broker Hub's DEMO card
      (`app_ui/views/broker_hub_page.py`: two `EchoMode.Password`
      `QLineEdit`s + "Save credentials", cleared after every submit attempt)
      wired to a new `BrokerHubController.store_credentials()`
      (`app_ui/controllers/broker_hub.py`) that mirrors
      `entrypoints/headless.py::_demo_store_creds` exactly — same
      `KEYRING_SERVICE = "AutoTradeAI"`, same `f"{account_id}:api_key"` /
      `f"{account_id}:api_secret"` keyring keys, same "create
      `Account(status=NEW, eligibility=INELIGIBLE, is_active=False)` only if
      one doesn't already exist, never overwrite an existing row" shape — so
      the CLI and the UI never disagree about where a DEMO credential lives.
      `BrokerHubState` gained `demo_credentials_configured` (presence-only,
      via `load_secret(...) is not None`, same split as
      `SettingsController.telegram_configured()`); Test connection / Enable
      DEMO reuse the existing `can_enable_demo`/`cert_gate_reason`
      setEnabled+setToolTip idiom (new `demo_ready_for_connection` /
      `credentials_gate_reason` properties) to explain "store credentials
      first" instead of a second disabled-state mechanism. Also added the
      G7 step 5/6 VERIFIED/DENIED/UNKNOWN verdict to
      `BrokerHubController.test_connection` (`ConnectionTestResult.verdict`,
      surfaced in the audit payload and the Broker Hub test-result label):
      VERIFIED on a clean `connect()`+`get_capabilities()`, DENIED only for
      an exception whose type name looks like ccxt's real
      `AuthenticationError`/`PermissionDenied` family (checked by class name,
      not a `ccxt` import — the UI layer must never import `ccxt`), UNKNOWN
      otherwise. Honest limitation: `FakeCcxtExchange`'s `fail_auth`
      sentinel raises a plain `RuntimeError`, so DENIED is not reachable
      through any fake/mock in this codebase today — only through a real
      ccxt client raising a real typed auth error. Withdraw-permission
      detection (G7 step 6, LIVE-only) remains out of scope; no such API
      surface exists in the fake/real adapter.
      Tests: `tests/unit/test_broker_hub_controller.py`,
      `tests/integration/test_broker_hub_ui.py` (both suites gained an
      autouse `FakeKeyring` fixture — mirrors
      `test_settings_controller.py`/`test_settings_ui.py`'s — since every
      `snapshot()` call now reads the keyring for
      `demo_credentials_configured`; neither suite touched keyring at all
      before this fix).

- [x] T072 **FR-005 gap**: `contracts/packaged-ops.md` requires "Restore:
      refuse if schema_meta incompatible; never restore plaintext secrets"
      but only `persistence/backup.py::snapshot_database` existed — restore
      was entirely unimplemented (zero matches anywhere in the repo for
      `restore_database`/`restore_backup`). Investigation finding: the ORM's
      `SchemaMeta` model (`schema_meta` table) is registered with Alembic's
      metadata and its table is created by migration `0001_adr_d03_1`, but
      no migration and no application code anywhere ever INSERTs a row into
      it — verified by grepping the entire `src/` tree. It is dead schema,
      always empty in practice, so the real compatibility signal is
      Alembic's own internal `alembic_version` table (a separate, standard
      table Alembic stamps automatically on every `upgrade`). Fixed by
      adding `persistence/backup.py::restore_database` (mirrors
      `snapshot_database`'s SQLite backup API + `PRAGMA integrity_check` +
      explicit-close-before-filesystem-op pattern): refuses on a corrupt
      backup, refuses unless the backup's `alembic_version` exactly equals
      `alembic.script.ScriptDirectory.get_current_head()` (no
      forward-migration-on-restore), takes a safety snapshot of the current
      target DB before overwriting it (reuses `snapshot_database`, skipped
      only when the target doesn't exist yet), then commits atomically via
      `Path.replace` with a fallback to an in-place SQLite-backup-API
      overwrite when `Path.replace` raises `PermissionError` — verified
      empirically that this happens on Windows whenever the target is held
      open by another connection (e.g. the same running app's own live
      SQLAlchemy engine), since SQLite's Windows VFS does not open files
      with `FILE_SHARE_DELETE` even for an idle, no-transaction connection;
      restoring from inside the running app is the normal case here, not an
      edge case. Also found and fixed a related bug while building the
      safety-snapshot step: `snapshot_database`'s 1-second-resolution
      stamped filenames plus its same-directory default meant a safety
      snapshot taken *before* reading the backup source could, on a
      same-timestamp collision, silently overwrite the backup file being
      restored from, turning the restore into a no-op — fixed by reordering
      `restore_database` to fully capture+verify the backup source into an
      independent temp file *before* ever taking the safety snapshot.
      Never touches the OS keyring — secrets were never in SQLite to begin
      with, so nothing needs restoring there;
      `persistence.secrets.load_secret` already returns `None` gracefully
      for any keyring ref the restored DB references that doesn't exist on
      this machine. Wired into `SettingsController.run_restore` (mirrors
      `run_backup`'s shape; defaults to the real runtime path, tests always
      inject `db_path`) and `SettingsPage` ("Restore from backup..."
      button: `QFileDialog` scoped to the backups directory → REQUIRED
      Yes/No confirm dialog naming the safety-backup behavior, default No,
      exact idiom as Kill-switch's Flatten confirm → on success tells the
      Owner to restart the app, no in-process engine reconnection
      attempted).
      Tests: `tests/unit/test_backup.py` (new file — `snapshot_database`
      had no dedicated unit tests before this either), extended
      `tests/unit/test_settings_controller.py` and
      `tests/integration/test_settings_ui.py`.

- [x] T073 **Cross-reference (D1a-scoped gap, fixed there)**: the
      `IntentState.CANCEL_REQUESTED`/`CANCEL_UNKNOWN` FSM-states-with-no-
      driving-code gap (new `core/oms/cancel.py::cancel_intent` +
      `autotrade-headless cancel-intent --intent-id <id>` CLI + new
      terminal `IntentState.CANCELED`) is recorded in full under
      `specs/001-d1a-paper-core/tasks.md` T066, since it's a D1a fault-
      matrix ("cancel timeout + late fill") gap, not a D1c one. Confirmed
      as part of that fix: D1c's Live Monitor
      (`app_ui/services/dashboard.py::INFLIGHT_INTENT_STATES`) already
      listed `CANCEL_UNKNOWN`, so it already surfaced a lingering cancel
      correctly — no `app_ui/` change was made or needed. No new UI
      affordance was added (a cancel button is a separate, bigger decision
      than this task's scope covered) — cancellation is CLI-only for now,
      same posture as T041's deliberate "no blind-retry/resubmit button"
      on Live Monitor.

- [x] T074 **Cross-reference (D1a-scoped gap, fixed there)**: ADR-D12
      (clock-skew/monotonic-timeout detection) — real detection logic and
      its fault test are recorded in full under
      `specs/001-d1a-paper-core/tasks.md` T071, since it's a D1a fault-
      matrix ("sleep/resume or wall-clock jump") gap, not a D1c one. The
      desktop-side wiring lands in this tree only because that's where the
      integration point already lives: new
      `core/domain/clock.py::detect_clock_jump` (pure, Qt-free — backward-
      wall-clock check is cross-restart-safe; monotonic-vs-wall divergence
      check is same-process-only, by construction of `time.monotonic()`),
      new `app_ui/services/clock_checkpoint.py`
      (`read_last_wall_checkpoint`/`write_wall_checkpoint`, `AppSetting`-
      backed, same reuse pattern as `app_ui/services/settings.py`'s
      autostart preference — no new table/migration), wired into
      `app_ui/services/startup.py::run_desktop_startup_recovery` (checks
      the persisted checkpoint at every launch; locks the `AccountGate`
      through the same `gate.lock(...)` path Startup Recovery already uses
      on a detected backward jump; advances the checkpoint only after a
      fully successful, non-locked recovery). Evaluated adding a `QTimer`
      to `MainWindow` (`app_ui/views/main_window.py`) to get a second,
      same-process checkpoint for the monotonic-divergence check — would
      have been the first `QTimer` anywhere in `app_ui/` (no existing
      precedent) and would also need to re-lock a *running* session
      (banner refresh, blocking further trading mid-session), which is
      more surface than this fix's blast radius warrants on its own;
      scoped OUT and flagged as follow-up. `detect_clock_jump`'s
      monotonic-divergence check is fully implemented and unit-tested
      regardless — only the periodic same-process caller is missing. No
      other `app_ui/` change was made or needed.

- [x] T075 **ADR-D03 gap**: `Kien-truc-App-Desktop-Solo-v1.4.md` line ~187
      ("Backup lịch dùng SQLite backup API vào file tạm →
      `integrity_check` → atomic rename; giữ mặc định 7 bản") was only
      half-built — `persistence/backup.py::snapshot_database` took a new
      timestamped backup every call but never deleted old ones, so the
      `backups/` directory grew without bound. Confirmed "7" is the exact,
      Owner-signed-off default (same doc ~line 913, D0-08: "Backup 7 bản /
      log 30 ngày ... Chấp nhận mặc định" — not a rough guess). Fixed by
      adding `persistence/backup.py::rotate_backups(backup_dir, *,
      keep=DEFAULT_BACKUP_RETENTION)` (new module constant
      `DEFAULT_BACKUP_RETENTION = 7`): lists files matching the exact
      `autotrade-<timestamp>.sqlite3` naming pattern `snapshot_database`
      writes (never a broad glob — a `.tmp` file mid-write or an unrelated
      file in the same directory is never a candidate), sorts by the
      timestamp *embedded in the filename* (not filesystem mtime, which is
      unreliable across copies/restores), deletes all but the newest
      `keep`, and never raises — a delete failure on one file is skipped so
      it can't block cleanup of the rest or undo the fact that a good
      backup was just taken. Wired into `snapshot_database` itself (runs
      once at the end of every successful snapshot) rather than only from
      `SettingsController.run_backup`, so every caller gets rotation for
      free — including `restore_database`'s internal pre-overwrite safety
      snapshot, which lands in the same `backups/` directory by default and
      is, deliberately, subject to the same 7-file cap: a safety-snapshot-
      before-restore is still "a backup" per ADR-D03's wording, and
      exempting it would let repeated restores silently grow the directory
      without bound even though each individual file still looks like a
      normal, valid backup. `snapshot_database` also gained an injectable
      `now: datetime | None = None` parameter (same pattern as
      `app_ui/services/dashboard.py::build_dashboard_view`'s `now`) purely
      to make rotation tests deterministic without sleeping between calls
      or fighting the stamped filenames' 1-second resolution; real callers
      never pass it. New `persistence/backup.py::list_backups` (small
      helper sharing the same file-matching/ordering logic as
      `rotate_backups`) backs a minimal Settings UI addition:
      `SettingsController.run_backup`'s `BackupResult` gained a `kept: int
      | None` field, and `SettingsPage`'s backup result label now appends
      `(N backup(s) kept)` — no other UI change, the Backup section was not
      redesigned.
      **Explicit scoping decision (same visibility treatment as T074's
      clock-skew-timer deferral):** the doc phrase "Backup lịch" implies a
      SCHEDULED/automatic periodic backup trigger, which is a separate,
      larger feature (needs a timer/scheduling mechanism, same kind of
      surface as the deferred clock-skew periodic timer — see
      `specs/003-d1c-desktop-mvp/OWNER-D1C-OPS-SOAK.md`'s "Sleep / resume"
      section). This task is scoped to **retention rotation only**, applied
      every time a backup is taken through the existing manual trigger
      (Settings' "Backup now" button / a restore's safety snapshot). No
      `QTimer`, no background thread, and no "N days since last backup"
      auto-trigger were added — that remains a separate, deliberately
      out-of-scope decision, not silently declined. Also checked whether
      "Trước migration luôn tạo snapshot" (always snapshot before a
      migration runs) is implemented anywhere: it is not —
      `persistence/alembic/env.py::run_migrations_online`/
      `run_migrations_offline` call `context.run_migrations()` directly,
      no `snapshot_database` call anywhere in that file or its callers.
      Left untouched deliberately: migrations run against a live DB path
      resolved from environment state (`AUTOTRADE_DATA_DIR`/
      `AUTOTRADE_DATABASE_URL`/`%LOCALAPPDATA%`), including in test/CI
      contexts that intentionally point at throwaway `tmp_path` databases
      with no `backups/` directory conventions of their own — adding a
      snapshot call there needs its own review of failure/rollback
      semantics (what happens if the pre-migration snapshot itself fails
      mid-`alembic upgrade`?) rather than being folded into a UI-triggered-
      backup fix. Filed here as a smaller, separate finding, not built.
      Tests: extended `tests/unit/test_backup.py` (`rotate_backups` keeps
      newest N / no-op under the cap / ignores non-backup files / survives
      a per-file delete failure without raising; `snapshot_database`
      end-to-end via 9 injected-`now` calls collapsing to 7 files).
      `pytest -m "d1a or d1b"` (100 passed, 2 skipped) and `pytest -m d1c`
      (222 passed, 2 skipped) both stayed green; `ruff check` clean on all
      changed files.

---

## Phase 4: Ops soak D1c (≥14d) — after MVP UI

- [x] T060 Operational soak runbook (≥14d) separate from D1b 72h — `specs/003-d1c-desktop-mvp/OWNER-D1C-OPS-SOAK.md`
- [x] T061 Fill matrix G6 / ADR-D13 packaged Evidence — the ≥14d wall-clock window itself is still an Owner action pending against a real machine, tracked in the runbook above, not by this checkbox

---

## Parallel notes

- T001–T006 are the only code tasks intended **during** D1b V8 soak.
- Do not start second `run-soak` on Owner machine.
