# Quickstart: D1c Desktop MVP (docs phase)

**Gate**: D1b certification `valid=true` trước E2E UI DEMO.

## Now (docs only)

```text
# Đọc
specs/003-d1c-desktop-mvp/spec.md
specs/003-d1c-desktop-mvp/plan.md
```

## Later (sau D1b exit)

```text
# stub (không cần Qt)
autotrade-desktop
# → exit 2 + hướng dẫn pip install -e ".[ui]" nếu thiếu PySide6

# sau /speckit-implement MainWindow + D1b valid
pip install -e ".[ui]"
pytest -m "d1a or d1b"   # regression
pytest -m d1c            # UI/packaged khi có
```

## Out of scope here

LIVE, AI Center, Backtest UI, multi-exchange.
