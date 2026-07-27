"""Qt-free UI controllers (D1c).

Views own pixels; controllers own the call into `core.*`. Keeping them apart
means the Pause / snapshot logic is unit-testable without a display server or
PySide6 installed. Enforced by `tests/unit/test_ui_import_boundaries.py`.
"""
