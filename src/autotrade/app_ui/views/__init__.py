"""Qt view layer (D1c) — the ONLY package allowed to import PySide6.

Importing anything here requires the optional extra::

    pip install -e ".[ui]"

Views must not talk to SQLAlchemy or ccxt directly; they go through
`autotrade.app_ui.controllers` / `autotrade.app_ui.services`.
"""
