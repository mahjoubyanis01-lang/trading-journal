"""Resource/data path resolution that works in dev AND when frozen (PyInstaller).

- In development, resources live in the repo (``trading-hub/frontend/dist``,
  ``trading-hub/assets``).
- In a PyInstaller build they are unpacked under ``sys._MEIPASS``.
- Writable data (the SQLite DB, MT5 instances) must go to a real user folder,
  never the read-only bundle.
"""
from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_base() -> Path:
    """Base folder that contains ``frontend/`` and ``assets/``."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    # backend/app/paths.py -> trading-hub/
    return Path(__file__).resolve().parents[2]


def frontend_dist() -> Path:
    return resource_base() / "frontend" / "dist"


def assets_dir() -> Path:
    return resource_base() / "assets"


def user_data_dir() -> Path:
    """Writable per-user data dir (used when frozen)."""
    if sys.platform == "win32":
        import os

        base = Path(os.environ.get("APPDATA", Path.home())) / "TradingHub"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "TradingHub"
    else:
        base = Path.home() / ".local" / "share" / "trading-hub"
    base.mkdir(parents=True, exist_ok=True)
    return base
