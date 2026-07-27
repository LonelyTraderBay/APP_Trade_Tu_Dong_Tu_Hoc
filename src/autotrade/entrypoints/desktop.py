"""Desktop entrypoint (D1c) — optional PySide6.

Does not start a localhost HTTP API (ADR-D13). T014 wires the MainWindow +
tray; the trading screens themselves stay empty until Phase 3 clears the D1b
certification gate.

Exit codes:
  0  clean exit
  2  optional extra [ui] (PySide6) not installed
  3  another instance already holds the single-instance lock
"""

from __future__ import annotations

import sys

EXIT_OK = 0
EXIT_NO_UI_EXTRA = 2
EXIT_ALREADY_RUNNING = 3

_MISSING_UI_MESSAGE = (
    "autotrade-desktop requires optional extra [ui].\n"
    '  pip install -e ".[ui]"\n'
    "Trading core remains available via autotrade-headless."
)


def _build_controller():  # noqa: ANN202 - concrete type needs the DB layer
    from autotrade.app_ui.controllers.tray import TrayController
    from autotrade.persistence.engine import create_sqlite_engine, default_db_path
    from autotrade.persistence.uow import UnitOfWork

    return TrayController(UnitOfWork(create_sqlite_engine(default_db_path())))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    check_only = "--check" in args

    try:
        import PySide6  # noqa: F401
    except ImportError:
        print(_MISSING_UI_MESSAGE, file=sys.stderr)
        return EXIT_NO_UI_EXTRA

    # Guard AFTER the extra check so the failure path stays side-effect free,
    # but BEFORE QApplication so a second instance never builds a window.
    from autotrade.app_ui.services.single_instance import (
        SingleInstanceGuard,
        read_owner_pid,
    )

    guard = SingleInstanceGuard()
    if not guard.acquire():
        owner = read_owner_pid(guard.lock_path)
        suffix = "" if owner is None else f" (pid {owner})"
        print(
            f"autotrade-desktop is already running{suffix} — "
            "use the tray icon to open it.",
            file=sys.stderr,
        )
        return EXIT_ALREADY_RUNNING

    try:
        controller = _build_controller()
        if check_only:
            try:
                banner = controller.snapshot().account.banner
            except Exception as exc:  # noqa: BLE001 - report, do not crash
                banner = f"session unavailable ({type(exc).__name__})"
            print(f"autotrade-desktop: ready — {banner}")
            return EXIT_OK
        return _run_gui(controller)
    finally:
        guard.release()


def _run_gui(controller) -> int:  # noqa: ANN001 - TrayController, Qt-free import above
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon

    from autotrade.app_ui.views.main_window import MainWindow
    from autotrade.app_ui.views.tray import AppTray

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("AutoTrade AI")
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow(controller)
    window.show()

    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = AppTray(controller, window)
        tray.quit_action.triggered.connect(app.quit)
        tray.show()
    else:
        # No tray on this desktop: closing the window must still quit.
        app.setQuitOnLastWindowClosed(True)

    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
