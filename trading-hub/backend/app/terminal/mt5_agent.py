"""Windows MT5 agent (§13-15, §21) - the real instance/terminal machinery.

This is the part that only works on the user's Windows PC. It:

1. locates an installed MetaTrader 5 (registry + common install dirs);
2. creates a dedicated *portable* instance per account by copying the terminal
   into its own folder, so N accounts run N isolated terminals that never mix
   data (§14-15);
3. launches / terminates / checks that terminal process;
4. installs an Expert Advisor (.ex5) into the instance's ``MQL5/Experts`` and
   drops a chart template (§16-18, §21).

On any non-Windows machine every method degrades to a clear "unavailable"
result instead of pretending (§88). The MT5 *connection* itself is done by
MT5Connector via the official ``MetaTrader5`` package, pointed at the instance
produced here.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from ..core.config import get_settings

log = logging.getLogger("trading_hub.mt5_agent")

IS_WINDOWS = sys.platform == "win32"

# Repo-bundled MQL assets (companion bridge EA) - works in dev and frozen.
from ..paths import assets_dir as _assets_dir

ASSETS_DIR = _assets_dir()

# Common 64-bit install locations to probe when the registry lookup misses.
_COMMON_DIRS = [
    r"C:\Program Files\MetaTrader 5",
    r"C:\Program Files\FundedNext MetaTrader 5",
    r"C:\Program Files\FTMO MetaTrader 5",
]


@dataclass(slots=True)
class InstancePaths:
    instance_id: str
    root: Path
    terminal_exe: Path
    data_path: Path


def _instances_root() -> Path:
    root = get_settings().data_dir / "mt5_instances"
    root.mkdir(parents=True, exist_ok=True)
    return root


def find_mt5_install() -> Path | None:
    """Locate a base MT5 installation (the folder with terminal64.exe)."""
    if not IS_WINDOWS:
        return None
    # 1) Windows registry (where the installer records the path).
    try:  # pragma: no cover - Windows only
        import winreg

        for hive, key in (
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\MetaQuotes\Terminal"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\MetaQuotes\Terminal"),
        ):
            try:
                with winreg.OpenKey(hive, key) as k:
                    i = 0
                    while True:
                        sub = winreg.EnumKey(k, i)
                        cand = Path(sub) / "terminal64.exe"
                        if cand.exists():
                            return cand.parent
                        i += 1
            except OSError:
                continue
    except Exception:  # noqa: BLE001
        pass
    # 2) Common install dirs.
    for d in _COMMON_DIRS:  # pragma: no cover - Windows only
        exe = Path(d) / "terminal64.exe"
        if exe.exists():
            return exe.parent
    return None


def create_instance(instance_id: str) -> InstancePaths | None:
    """Create a portable per-account terminal instance (§15).

    Returns None when MT5 isn't installed / not on Windows - the caller then
    surfaces "platform unavailable" rather than fabricating paths (§88)."""
    base = find_mt5_install()
    if base is None:
        return None
    root = _instances_root() / instance_id
    data_path = root
    terminal_exe = root / "terminal64.exe"
    if not terminal_exe.exists():  # pragma: no cover - Windows only
        root.mkdir(parents=True, exist_ok=True)
        # Copy the minimal set needed for a portable terminal.
        for name in ("terminal64.exe", "metaeditor64.exe"):
            src = base / name
            if src.exists():
                shutil.copy2(src, root / name)
        # MQL5 tree so we can drop EAs/templates into this instance only.
        (root / "MQL5" / "Experts").mkdir(parents=True, exist_ok=True)
        (root / "MQL5" / "Profiles" / "Charts" / "Default").mkdir(parents=True, exist_ok=True)
        (root / "templates").mkdir(parents=True, exist_ok=True)
    return InstancePaths(instance_id, root, terminal_exe, data_path)


def launch(paths: InstancePaths) -> int | None:
    """Launch the portable terminal; return the OS pid (§13)."""
    if not IS_WINDOWS:
        return None
    try:  # pragma: no cover - Windows only
        proc = subprocess.Popen(
            [str(paths.terminal_exe), "/portable"],
            cwd=str(paths.root),
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
        )
        return proc.pid
    except Exception:  # noqa: BLE001
        log.exception("failed to launch MT5 instance %s", paths.instance_id)
        return None


def is_process_alive(pid: int | None) -> bool:
    if not pid or not IS_WINDOWS:
        return False
    try:  # pragma: no cover - Windows only
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True
        )
        return str(pid) in out.stdout
    except Exception:  # noqa: BLE001
        return False


def terminate(pid: int | None) -> None:
    if not pid or not IS_WINDOWS:
        return
    try:  # pragma: no cover - Windows only
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    except Exception:  # noqa: BLE001
        pass


def install_robot(paths: InstancePaths, robot_file: str | None) -> bool:
    """Copy an EA into this instance's Experts folder (§21)."""
    if robot_file is None:
        return False
    src = Path(robot_file)
    if not src.exists():
        log.warning("robot file not found: %s", robot_file)
        return False
    dst = paths.root / "MQL5" / "Experts" / src.name
    try:  # pragma: no cover - Windows only
        os.makedirs(dst.parent, exist_ok=True)
        shutil.copy2(src, dst)
        return True
    except Exception:  # noqa: BLE001
        log.exception("failed to install robot into %s", paths.instance_id)
        return False


def apply_template(paths: InstancePaths, template_dir: str | None) -> bool:
    """Copy a chart template/profile into this instance (§16-18)."""
    if not template_dir:
        return False
    src = Path(template_dir)
    if not src.exists():
        return False
    try:  # pragma: no cover - Windows only
        for f in src.glob("*.tpl"):
            shutil.copy2(f, paths.root / "templates" / f.name)
        return True
    except Exception:  # noqa: BLE001
        return False


def install_bridge(paths: InstancePaths) -> bool:
    """Install + compile the TradingHubBridge companion EA into the instance,
    so heartbeat/account reporting and RUN/STOP work (§21, §66)."""
    src = ASSETS_DIR / "mt5" / "TradingHubBridge.mq5"
    if not src.exists():
        return False
    experts = paths.root / "MQL5" / "Experts"
    experts.mkdir(parents=True, exist_ok=True)
    dst = experts / src.name
    try:  # pragma: no cover - Windows only
        shutil.copy2(src, dst)
        compile_ea(paths, dst)
        return True
    except Exception:  # noqa: BLE001
        log.exception("failed to install bridge EA")
        return False


def compile_ea(paths: InstancePaths, source: Path) -> bool:
    """Compile an .mq5 to .ex5 with MetaEditor (§21)."""
    if not IS_WINDOWS:
        return False
    editor = paths.root / "metaeditor64.exe"
    if not editor.exists():
        return False
    try:  # pragma: no cover - Windows only
        subprocess.run(
            [str(editor), f"/compile:{source}", "/log"],
            capture_output=True, timeout=120,
        )
        return source.with_suffix(".ex5").exists()
    except Exception:  # noqa: BLE001
        return False
