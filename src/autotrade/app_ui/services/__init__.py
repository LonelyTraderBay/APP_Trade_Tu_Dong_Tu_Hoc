"""Qt-free UI services (D1c).

Everything in this package MUST stay importable without PySide6 installed:
it is the read-model / command layer the Qt views call into. Enforced by
`tests/unit/test_ui_import_boundaries.py`.
"""
