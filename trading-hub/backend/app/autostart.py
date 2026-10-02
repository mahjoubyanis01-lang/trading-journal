"""Start Trading Hub automatically with Windows (§65).

Drops a small launcher into the current user's Startup folder so the app (and
its background engine) comes up on login. CLI:

    python -m app.autostart enable
    python -m app.autostart disable
    python -m app.autostart status

No admin rights needed (per-user Startup folder). On non-Windows it's a no-op
with a clear message.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_LAUNCHER_NAME = "TradingHub.cmd"


def _startup_dir() -> Path | None:
    if sys.platform != "win32":
        return None
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _project_launcher() -> Path:
    # trading-hub/TradingHub.bat (two levels up from backend/app)
    return Path(__file__).resolve().parents[2].parent / "TradingHub.bat"


def enable() -> str:
    d = _startup_dir()
    if d is None:
        return "Auto-start is only available on Windows."
    d.mkdir(parents=True, exist_ok=True)
    target = _project_launcher()
    shortcut = d / _LAUNCHER_NAME
    shortcut.write_text(f'@echo off\r\nstart "" "{target}"\r\n', encoding="utf-8")
    return f"Auto-start enabled: {shortcut}"


def disable() -> str:
    d = _startup_dir()
    if d is None:
        return "Auto-start is only available on Windows."
    shortcut = d / _LAUNCHER_NAME
    if shortcut.exists():
        shortcut.unlink()
        return "Auto-start disabled."
    return "Auto-start was not enabled."


def status() -> str:
    d = _startup_dir()
    if d is None:
        return "unavailable (not Windows)"
    return "enabled" if (d / _LAUNCHER_NAME).exists() else "disabled"


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    print({"enable": enable, "disable": disable, "status": status}.get(action, status)())
