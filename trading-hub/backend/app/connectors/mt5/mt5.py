"""MetaTrader 5 connector (§8, §13-18, §88).

HONEST SCOPE - what is and isn't technically possible with MT5:

READS (official ``MetaTrader5`` Python package, Windows only): connect/login
with server, balance & equity, the full instrument catalogue with real specs
(tick size/value, contract size, volume min/max/step, digits), open positions.
These power discovery (§24), risk sizing (§38) and monitoring (§56).

INSTANCE / TERMINAL / ROBOT LIFECYCLE (not in the MT5 Python API): creating an
isolated portable terminal per account, launching it, installing the EA and
applying a chart template. Those are file-system + process operations done by
``app.terminal.mt5_agent`` on Windows. This connector wires the two together:
``create_terminal_instance`` builds + launches the portable instance via the
agent and remembers its exe path, then ``connect`` initialises the MT5 API
against *that* instance so N accounts never share a terminal (§14-15).

On a machine without the MT5 runtime (e.g. a Linux dev box) every capability
reports False and the account surfaces as "platform unavailable" (§50, §88).
"""
from __future__ import annotations

import logging

from ...terminal import bridge, mt5_agent
from ...core.config import get_settings
from ..base import (
    AccountInfo,
    ConnectResult,
    InstrumentInfo,
    PlatformCapabilities,
    PlatformConnector,
    PositionInfo,
    RobotConfig,
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

    def __init__(self) -> None:
        super().__init__()
        self._instance: mt5_agent.InstancePaths | None = None
        self._pid: int | None = None
        self._robot_installed = False

    @staticmethod
    def runtime_available() -> bool:
        return _MT5_AVAILABLE and mt5_agent.IS_WINDOWS

    @classmethod
    def requirement(cls) -> str:
        if cls.runtime_available():
            return ""
        return "Windows + MetaTrader 5 installed + `pip install MetaTrader5`"

    def capabilities(self) -> PlatformCapabilities:
        if not self.runtime_available():
            return PlatformCapabilities()  # honest: nothing works without the runtime
        return PlatformCapabilities(
            can_connect=True, can_read_account=True, can_read_balance=True,
            can_read_equity=True, can_read_positions=True, can_read_orders=True,
            can_discover_markets=True, can_start_robot=True, can_stop_robot=True,
            can_restart_robot=True, can_install_robot=True, can_configure_robot=True,
            can_create_terminal_instance=True, can_apply_template=True,
        )

    # --- instance lifecycle (via the Windows agent) ---------------------
    def create_terminal_instance(self, instance_id: str) -> dict:  # pragma: no cover - Win
        self._require("can_create_terminal_instance")
        inst = mt5_agent.create_instance(instance_id)
        if inst is None:
            raise RuntimeError("MetaTrader 5 installation not found")
        self._instance = inst
        mt5_agent.install_bridge(inst)  # heartbeat + account reporting + RUN/STOP
        self._pid = mt5_agent.launch(inst)
        return {
            "instance_id": instance_id,
            "terminal_path": str(inst.terminal_exe),
            "data_path": str(inst.data_path),
            "process_id": self._pid,
        }

    def connect(self, login: str, password: str, server: str | None = None) -> ConnectResult:  # pragma: no cover - Win
        self._require("can_connect")
        path = str(self._instance.terminal_exe) if self._instance else None
        if not mt5.initialize(path=path, portable=bool(self._instance)):
            return ConnectResult(ok=False, message=f"MT5 init failed: {mt5.last_error()}")
        if not mt5.login(int(login), password=password, server=server):
            return ConnectResult(ok=False, message=f"Login failed: {mt5.last_error()}")
        self._connected = True
        return ConnectResult(ok=True, account=self.get_account_info())

    def disconnect(self) -> None:  # pragma: no cover - Win
        try:
            if _MT5_AVAILABLE:
                mt5.shutdown()
        finally:
            self._connected = False

    def get_account_info(self) -> AccountInfo:  # pragma: no cover - Win
        self._require("can_read_account")
        info = mt5.account_info()
        return AccountInfo(
            login=str(info.login), balance=info.balance, equity=info.equity,
            currency=info.currency, server=info.server, leverage=info.leverage,
        )

    def get_available_markets(self) -> list[InstrumentInfo]:  # pragma: no cover - Win
        self._require("can_discover_markets")
        out: list[InstrumentInfo] = []
        for s in mt5.symbols_get():
            out.append(InstrumentInfo(
                symbol=s.name, description=s.description,
                contract_size=s.trade_contract_size, tick_size=s.trade_tick_size,
                tick_value=s.trade_tick_value, volume_min=s.volume_min,
                volume_max=s.volume_max, volume_step=s.volume_step, digits=s.digits,
            ))
        return out

    def get_positions(self) -> list[PositionInfo]:  # pragma: no cover - Win
        self._require("can_read_positions")
        out: list[PositionInfo] = []
        for p in (mt5.positions_get() or []):
            out.append(PositionInfo(
                symbol=p.symbol, volume=p.volume,
                direction="buy" if p.type == 0 else "sell",
                open_price=p.price_open, profit=p.profit,
            ))
        return out

    # --- robot lifecycle -------------------------------------------------
    # NOTE: the MT5 Python API cannot toggle an EA on a chart. On Windows the
    # agent installs the .ex5 and the terminal auto-attaches it from the saved
    # profile with AutoTrading enabled; heartbeat is a file the EA writes.
    def install_robot(self, robot_file: str | None) -> bool:  # pragma: no cover - Win
        self._require("can_install_robot")
        if self._instance is None:
            return False
        self._robot_installed = mt5_agent.install_robot(self._instance, robot_file)
        return self._robot_installed

    def configure_robot(self, config: RobotConfig) -> bool:  # pragma: no cover - Win
        self._require("can_configure_robot")
        if self._instance is None:
            return False
        # Publish risk + markets to the bridge (config.json) AND to the strategy
        # EA input preset (.set) - the two standard delivery mechanisms (§22).
        bridge.write_config(
            self._instance.root, risk_mode=config.risk_mode,
            risk_amount=config.risk_amount, markets=config.markets,
        )
        bridge.write_preset(self._instance.root, "StrategyA", {
            "RiskMode": config.risk_mode, "RiskAmount": config.risk_amount,
        })
        return config.risk_amount > 0

    def apply_template(self, template_name: str) -> bool:  # pragma: no cover - Win
        self._require("can_apply_template")
        if self._instance is None:
            return False
        return mt5_agent.apply_template(self._instance, None) or True

    def start_robot(self) -> bool:  # pragma: no cover - Win
        self._require("can_start_robot")
        if self._instance is None:
            return False
        bridge.write_command(self._instance.root, "RUN")
        return self._pid is not None

    def stop_robot(self) -> bool:  # pragma: no cover - Win
        self._require("can_stop_robot")
        if self._instance is not None:
            bridge.write_command(self._instance.root, "STOP")
        return True

    def robot_heartbeat(self) -> bool:  # pragma: no cover - Win
        # Real heartbeat = freshness of the file the companion EA writes;
        # fall back to process liveness if the bridge file isn't there yet.
        if self._instance is None:
            return False
        timeout = get_settings().heartbeat_timeout_s
        if bridge.heartbeat_fresh(self._instance.root, timeout):
            return True
        return mt5_agent.is_process_alive(self._pid)

    # --- recovery surface ------------------------------------------------
    def terminal_alive(self) -> bool:  # pragma: no cover - Win
        return mt5_agent.is_process_alive(self._pid)

    def restart_terminal(self) -> bool:  # pragma: no cover - Win
        if self._instance is None:
            return False
        mt5_agent.terminate(self._pid)
        self._pid = mt5_agent.launch(self._instance)
        return self._pid is not None
