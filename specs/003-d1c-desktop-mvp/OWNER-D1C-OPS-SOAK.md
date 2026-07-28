# Owner runbook — D1c operational soak (≥14 days)

**T060.** Owner-only wall-clock path, separate from D1b's 72h *trading-lifecycle*
soak (`specs/002-d1b-ccxt-demo/OWNER-D1B-EXIT.md`). D1b soaks the **DEMO
trading loop** (round-trips against testnet, tracked by `soak_runs` /
`autotrade-headless run-soak`). D1c soaks the **packaged desktop app itself**
— crash-free uptime, single-instance/sleep-resume behaviour, and that the
safety controls (Pause, Flatten, recon, backup) still work correctly after
days of real desktop use. There is no new DB table or CLI command for this —
it is an observational checklist, run against the one-folder build from
`packaging/build.py` on the Owner's own machine.

**Gate**: Phase 3 (T010–T053, all UI screens) merged and green — confirmed
`main` clean, `pytest -m "d1a or d1b"` and `pytest -m d1c` both pass. Do not
start the soak window against a build older than that.

## Before starting

- [ ] Fresh clean-machine install per `quickstart.md`'s "Clean-machine
      install checklist" (T022) — copy `dist/AutoTradeAI/` to the machine
      that will run the soak, do not soak the dev `.venv` build.
- [ ] `AutoTradeAI.exe --check` → exit 0, banner printed.
- [ ] Note the exact build: app version (`autotrade-headless --version`),
      commit hash, and soak start timestamp (local + UTC) in
      `docs/mvp-capability-matrix.md`'s G6 Evidence cell (T061) once the
      window completes — do not backdate.
- [ ] `%LOCALAPPDATA%\AutoTradeAI\` backed up (Settings → Backup now, or
      `snapshot_database`) before the window starts, so a Day-1 regression
      has a known-good rollback point.

## During the window (daily, or each real session)

- [ ] App has stayed open (or been reopened without error) since the last
      check — no crash dialog, no Windows Error Reporting popup.
- [ ] Tray icon still responds; tray **Pause** still works without a PIN
      prompt (contract: `pause_l1` is never PIN-gated — this must hold even
      after days of uptime, not just at launch).
- [ ] Dashboard banner still reads a sane mode/account/endpoint (not stuck
      on a stale snapshot from hours ago — `refresh()` should reflect
      current state each time a screen is shown).
- [ ] `%LOCALAPPDATA%\AutoTradeAI\autotrade.sqlite3` (or equivalent) size is
      growing sanely, not runaway (rough eyeball is enough — a genuine leak
      shows up over days, not a single check).
- [ ] No orphaned `AutoTradeAI.exe` processes in Task Manager after a normal
      close (single-instance lock must release cleanly on exit, not just on
      crash).

## Sleep / resume (at least 3 separate occasions across the window)

**Known gap, deliberately deferred — read before running this section.**
`detect_clock_jump()` (`core/domain/clock.py`) only catches a clock jump
**across a restart** (backward wall-clock vs. the last persisted
checkpoint). It does **not** run periodically while the app stays open
across a sleep/resume in the same process — that needs a `QTimer` plus a
design for re-locking a *running* session without ever blocking Pause/
Flatten (the no-PIN-ever invariant), which was scoped out as bigger than
the rest of the post-audit fixes (2026-07-27 decision, see PR #14). This
checklist section is the intentional substitute in the meantime: a human
checks the exact scenario the timer would have caught. If any of the
checks below actually fail during this soak — banner goes stale, KS/Live
Monitor shows something wrong post-resume, anything that traces back to
the clock jumping while the app was already running — **that is the
signal to build the periodic timer**, not before. File it as a new gap
with the concrete repro from this soak, don't preemptively build it on
spec.

- [ ] Put the machine to sleep with the app open; resume; app is still
      responsive (not frozen) and the mode/account banner still reflects
      reality — this is the "Startup Recovery subset" contract
      (`contracts/packaged-ops.md` §"Sleep / resume").
- [ ] After resume, tray Pause still works with no PIN.
- [ ] A second `AutoTradeAI.exe --check` launched right after resume still
      correctly refuses (exit 3) while the resumed instance holds the lock —
      resume must not silently drop the single-instance guard.

## Single-instance + headless coexistence (at least once)

- [ ] With the desktop app running, launch `autotrade-headless status` (or
      any subcommand) from the same machine — it must refuse with exit 3
      ("another instance is already running"), per the shared
      `AutoTradeAI.Solo` lock added this session (T015). Confirms the
      one-trading-process invariant holds for desktop+headless together, not
      only desktop-vs-desktop.

## Backup / restore (at least once, not just at window start)

- [ ] Settings → Backup now produces a new file under
      `%LOCALAPPDATA%\AutoTradeAI\backups\` and the shown path exists. The
      result label also reports how many backups now exist (e.g. "(3
      backup(s) kept)") — confirm that number never exceeds 7.
- [ ] `PRAGMA integrity_check` on that backup file returns `ok` (the backup
      helper already asserts this internally — spot-check manually once with
      `sqlite3 <backup file> "PRAGMA integrity_check;"` for the runbook
      record).
- [ ] After more than 7 manual backups have accumulated across the soak
      window (naturally, or by clicking "Backup now" a few extra times),
      confirm `backups\` never holds more than 7 `autotrade-*.sqlite3`
      files — `persistence.backup.rotate_backups` (ADR-D03's default of 7)
      deletes the oldest automatically on every new backup, including the
      safety snapshot a Restore takes before overwriting the live DB.

**Known gap, deliberately deferred — same treatment as the clock-skew
timer above.** ADR-D03 says "Backup lịch" (scheduled backup), which reads
as a periodic, automatic trigger — a `QTimer`/background-thread/"N days
since last backup" mechanism. That is **not** built. What exists today is
retention *rotation* only: every time a backup is taken through the
existing manual "Backup now" button (or a Restore's internal safety
snapshot), old backups beyond the newest 7 are pruned. Nothing in the app
takes a backup on its own on a schedule. If the ≥14-day soak surfaces a
real need for unattended periodic backups (e.g. the Owner routinely goes
several days without opening Settings), file that as a new gap with the
concrete scenario — don't build the timer preemptively on spec (2026-07-28
decision).

## Autostart (T053, once)

- [ ] Enable autostart in Settings; reboot the machine; confirm
      `AutoTradeAI.exe` actually launches on login (minimized/tray is fine).
- [ ] Disable autostart; reboot again; confirm it does **not** launch.

## End of window (≥14 days elapsed)

- [ ] No unresolved crash, no orphaned process, no runaway DB growth,
      sleep/resume held up across every occasion tested, single-instance
      held across desktop+headless.
- [ ] Record: soak start/end timestamps (local + UTC, not backdated), build
      version, machine spec (Win11 build number), and a one-line summary of
      any issue found (even minor) — into
      `docs/mvp-capability-matrix.md` G6 Evidence (T061).
- [ ] If anything failed: do **not** mark G6 evidence as passed — file the
      issue, fix, and restart the ≥14-day window against the fixed build.
      Do not average a bad day against otherwise-good days; this window
      exists to catch exactly the kind of slow-burn bug a short session
      can't.

## Out of scope for this runbook

LIVE trading, AI Center, Backtest UI, multi-exchange — same boundaries as
`quickstart.md`. This soak only covers the D1c desktop shell's operational
stability, not new trading logic (that's D1b's soak, already exited
2026-07-26 per `specs/002-d1b-ccxt-demo/OWNER-D1B-EXIT.md`).
