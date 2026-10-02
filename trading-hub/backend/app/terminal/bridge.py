"""Trading Hub <-> MetaTrader file bridge (§21, §66).

MetaTrader's Python API cannot drive an Expert Advisor, so Trading Hub and the
terminal talk through files inside the instance's ``MQL5/Files/TradingHub``
folder (``MQL4/Files/TradingHub`` on MT4). The companion EA
(``assets/mt5/TradingHubBridge.mq5``) runs on one chart and:

- reads ``config.json``  (risk mode + amount, markets, magic, enabled flag),
- reads ``command.txt``  ("RUN" / "STOP"),
- writes ``heartbeat.txt`` (unix seconds) every timer tick  -> real heartbeat,
- writes ``account.json`` (balance, equity, open positions) -> live monitoring.

This module is the Python side of that protocol. It is pure filesystem work,
OS-independent, and therefore fully unit-testable without MetaTrader present.
The actual EA ships under ``assets/`` and is installed by ``mt5_agent``.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

_SUBDIR = ("Files", "TradingHub")


def bridge_dir(instance_root: Path | str, mql: str = "MQL5") -> Path:
    """Folder the EA reads/writes (terminal-relative ``<MQL>/Files/TradingHub``)."""
    root = Path(instance_root) / mql
    d = root.joinpath(*_SUBDIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_config(
    instance_root: Path | str,
    *,
    risk_mode: str,
    risk_amount: float,
    markets: list[str],
    magic: int = 770001,
    enabled: bool = True,
    mql: str = "MQL5",
) -> Path:
    """Publish the robot configuration for the EA to pick up (§22)."""
    d = bridge_dir(instance_root, mql)
    payload = {
        "risk_mode": risk_mode,
        "risk_amount": round(float(risk_amount), 2),
        "markets": list(markets),
        "magic": int(magic),
        "enabled": bool(enabled),
        "updated": int(time.time()),
    }
    path = d / "config.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_command(instance_root: Path | str, command: str, mql: str = "MQL5") -> Path:
    """RUN / STOP relayed to the EA (§47 pause/start, §61 mass actions)."""
    command = command.upper().strip()
    if command not in {"RUN", "STOP"}:
        raise ValueError("command must be RUN or STOP")
    path = bridge_dir(instance_root, mql) / "command.txt"
    path.write_text(command, encoding="utf-8")
    return path


def write_preset(
    instance_root: Path | str, ea_name: str, params: dict, mql: str = "MQL5"
) -> Path:
    """Write an EA input preset (.set) so the strategy loads risk params on
    attach - the standard MetaTrader mechanism (§21)."""
    presets = Path(instance_root) / mql / "Presets"
    presets.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}={_fmt(v)}" for k, v in params.items()]
    path = presets / f"{ea_name}.set"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _fmt(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def read_heartbeat(instance_root: Path | str, mql: str = "MQL5") -> datetime | None:
    path = bridge_dir(instance_root, mql) / "heartbeat.txt"
    try:
        raw = path.read_text(encoding="utf-8").strip()
        return datetime.fromtimestamp(float(raw), tz=timezone.utc)
    except (FileNotFoundError, ValueError):
        return None


def heartbeat_fresh(
    instance_root: Path | str, timeout_s: int, now: datetime | None = None, mql: str = "MQL5"
) -> bool:
    hb = read_heartbeat(instance_root, mql)
    if hb is None:
        return False
    now = now or datetime.now(timezone.utc)
    return (now - hb).total_seconds() <= timeout_s


def read_account(instance_root: Path | str, mql: str = "MQL5") -> dict | None:
    path = bridge_dir(instance_root, mql) / "account.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
