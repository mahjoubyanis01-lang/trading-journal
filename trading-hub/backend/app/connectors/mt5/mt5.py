"""MetaTrader 5 connector (§8, §13-18, §88).

HONEST SCOPE - what is and isn't technically possible with MT5:

READS (fully supported by the official ``MetaTrader5`` Python package, Windows
only): connect/login, account balance & equity, the full instrument catalogue
with real specs (tick size/value, contract size, volume min/max/step, digits),
open positions and orders. These power discovery (§24), risk sizing (§38) and
monitoring (§56).

ROBOT & TERMINAL LIFECYCLE (NOT part of the MT5 Python API): MT5's API cannot
start/stop an Expert Advisor on a chart, create a new terminal instance, or
apply a chart template. Those are *file-system and process* operations handled
by the Windows :class:`TerminalManager` / :class:`RobotManager`:
  - a new instance = a portable copy of the terminal folder with its own
    ``MQL5`` data path, launched with ``/portable`` so instances never mix (§13-15);
  - installing a robot = copying the ``.ex5`` into ``MQL5/Experts`` and setting
    a startup profile/chart that auto-attaches it with AutoTrading on (§21);
  - heartbeat = a tiny companion EA writes a timestamp file the agent polls (§66);
  - templates = copying ``.tpl``/profile files into the instance (§16-18).

This class therefore declares read capabilities honestly, and *delegates*
robot/terminal capabilities to the platform agent. On a machine without the MT5
runtime (e.g. this Linux dev container) every capability reports False and the
UI shows the account as "platform unavailable" (§50) rather than pretending.
"""
from __future__ import annotations

import logging
import sys

from ..base import (
    AccountInfo,
    ConnectResult,
    InstrumentInfo,
    PlatformCapabilities,
    PlatformConnector,
)

log = logging.getLogger("trading_hub.connectors.mt5")

try:  # pragma: no cover - only importable on Windows with the package installed
    import MetaTrader5 as mt5  # type: ignore

    _MT5_AVAILABLE = True
except Exception:  # noqa: BLE001
    mt5 = None  # type: ignore[assignment]
    _MT5_AVAILABLE = False


class MT5Connector(PlatformConnector):
    key = "mt5"
    display_name = "MetaTrader 5"

    def __init__(self, terminal_path: str | None = None) -> None:
        super().__init__()
        self.terminal_path = terminal_path

    @staticmethod
    def runtime_available() -> bool:
        return _MT5_AVAILABLE and sys.platform == "win32"

    def capabilities(self) -> PlatformCapabilities:
        if not self.runtime_available():
            # Honest: nothing works without the Windows MT5 runtime (§88).
            return PlatformCapabilities()
        return PlatformCapabilities(
            can_connect=True, can_read_account=True, can_read_balance=True,
            can_read_equity=True, can_read_positions=True, can_read_orders=True,
            can_discover_markets=True,
            # delegated to the Windows TerminalManager / RobotManager:
            can_start_robot=True, can_stop_robot=True, can_restart_robot=True,
            can_install_robot=True, can_configure_robot=True,
            can_create_terminal_instance=True, can_apply_template=True,
        )

    def connect(self, login: str, password: str, server: str | None = None) -> ConnectResult:
        self._require("can_connect")
        if not mt5.initialize(path=self.terminal_path):  # pragma: no cover
            return ConnectResult(ok=False, message=f"MT5 init failed: {mt5.last_error()}")
        ok = mt5.login(int(login), password=password, server=server)  # pragma: no cover
        if not ok:
            return ConnectResult(ok=False, message=f"Login failed: {mt5.last_error()}")
        self._connected = True
        return ConnectResult(ok=True, account=self.get_account_info())

    def get_account_info(self) -> AccountInfo:  # pragma: no cover - needs runtime
        self._require("can_read_account")
        info = mt5.account_info()
        return AccountInfo(
            login=str(info.login), balance=info.balance, equity=info.equity,
            currency=info.currency, server=info.server, leverage=info.leverage,
        )

    def get_available_markets(self) -> list[InstrumentInfo]:  # pragma: no cover
        self._require("can_discover_markets")
        out: list[InstrumentInfo] = []
        for s in mt5.symbols_get():
            out.append(
                InstrumentInfo(
                    symbol=s.name, description=s.description,
                    contract_size=s.trade_contract_size, tick_size=s.trade_tick_size,
                    tick_value=s.trade_tick_value, volume_min=s.volume_min,
                    volume_max=s.volume_max, volume_step=s.volume_step, digits=s.digits,
                )
            )
        return out
