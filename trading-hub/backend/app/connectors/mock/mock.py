"""Mock / simulation connector (§70-71).

Implements every capability so the whole stack - add-account workflow, risk,
recovery, dashboard - runs end to end with no real platform, on any OS. It also
exposes fault-injection hooks (crash the terminal, kill the robot, drop the
heartbeat, lose the connection) so the recovery engine can be exercised (§71,
Tests 5 & 6).

Different brokers name the same instrument differently; the mock reproduces
this (EURUSD->EURUSDm, XAUUSD->GOLD, NASDAQ100->USTEC, ...) so the market
mapping engine has something real to resolve (§23-29).
"""
from __future__ import annotations

import random

from ...core.enums import AssetClass
from ..base import (
    AccountInfo,
    ConnectResult,
    InstrumentInfo,
    PlatformCapabilities,
    PlatformConnector,
    PositionInfo,
    RobotConfig,
)

# A realistic instrument universe. (symbol, description, asset, specs...)
_WORLD: list[InstrumentInfo] = [
    InstrumentInfo("EURUSDm", "Euro vs US Dollar", AssetClass.FOREX, "EUR", "USD",
                   100_000, 0.00001, 1.0, 0.01, 100.0, 0.01, 5),
    InstrumentInfo("GBPUSDm", "Great Britain Pound vs US Dollar", AssetClass.FOREX, "GBP", "USD",
                   100_000, 0.00001, 1.0, 0.01, 100.0, 0.01, 5),
    InstrumentInfo("USDJPYm", "US Dollar vs Japanese Yen", AssetClass.FOREX, "USD", "JPY",
                   100_000, 0.001, 0.67, 0.01, 100.0, 0.01, 3),
    InstrumentInfo("GOLD", "Gold vs US Dollar (XAUUSD)", AssetClass.METAL, "XAU", "USD",
                   100, 0.01, 1.0, 0.01, 50.0, 0.01, 2),
    InstrumentInfo("USTEC", "US Tech 100 index", AssetClass.INDEX, "USD", "USD",
                   1, 0.25, 0.25, 0.1, 50.0, 0.1, 2),
    InstrumentInfo("DJ30", "Wall Street 30 index", AssetClass.INDEX, "USD", "USD",
                   1, 1.0, 1.0, 0.1, 50.0, 0.1, 1),
    InstrumentInfo("BTCUSD", "Bitcoin vs US Dollar", AssetClass.CRYPTO, "BTC", "USD",
                   1, 0.01, 0.01, 0.01, 10.0, 0.01, 2),
]


class MockConnector(PlatformConnector):
    key = "mock"
    display_name = "Mock Platform"

    def __init__(self, seed_balance: float = 10_000.0) -> None:
        super().__init__()
        self._seed = seed_balance
        self._balance = seed_balance
        self._equity = seed_balance
        self._login = ""
        self._server = "Mock-Server-01"
        self._robot_running = False
        self._heartbeat_alive = False
        self._terminal_up = False
        # fault flags (set by the simulation harness)
        self._fault_connection = False
        self._fault_heartbeat = False

    # --- capabilities ----------------------------------------------------
    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            can_connect=True, can_read_account=True, can_read_balance=True,
            can_read_equity=True, can_read_positions=True, can_read_orders=True,
            can_discover_markets=True, can_start_robot=True, can_stop_robot=True,
            can_restart_robot=True, can_install_robot=True, can_configure_robot=True,
            can_create_terminal_instance=True, can_apply_template=True,
        )

    # --- connection ------------------------------------------------------
    def connect(self, login: str, password: str, server: str | None = None,
                extra: dict | None = None) -> ConnectResult:
        self._require("can_connect")
        if self._fault_connection:
            return ConnectResult(ok=False, message="Connection refused (simulated outage)")
        if not login or not password:
            return ConnectResult(ok=False, message="Missing credentials")
        self._login = login
        self._server = server or self._server
        self._connected = True
        return ConnectResult(ok=True, account=self.get_account_info())

    def get_account_info(self) -> AccountInfo:
        self._require("can_read_account")
        return AccountInfo(
            login=self._login or "0", balance=round(self._balance, 2),
            equity=round(self._equity, 2), currency="USD",
            server=self._server, broker="Mock Broker", leverage=100,
        )

    def get_available_markets(self) -> list[InstrumentInfo]:
        self._require("can_discover_markets")
        return list(_WORLD)

    def get_positions(self) -> list[PositionInfo]:
        self._require("can_read_positions")
        if not self._robot_running:
            return []
        return [PositionInfo("EURUSDm", 0.1, "buy", 1.0850, round(random.uniform(-20, 40), 2))]

    # --- terminal / template --------------------------------------------
    def create_terminal_instance(self, instance_id: str) -> dict:
        self._require("can_create_terminal_instance")
        self._terminal_up = True
        return {
            "instance_id": instance_id,
            "terminal_path": f"C:/MockMT5/{instance_id}/terminal64.exe",
            "data_path": f"C:/MockMT5/{instance_id}/data",
            "process_id": random.randint(1000, 9999),
        }

    def apply_template(self, template_name: str) -> bool:
        self._require("can_apply_template")
        return True

    # --- robot -----------------------------------------------------------
    def install_robot(self, robot_file: str | None) -> bool:
        self._require("can_install_robot")
        return True

    def configure_robot(self, config: RobotConfig) -> bool:
        self._require("can_configure_robot")
        return config.risk_amount > 0

    def start_robot(self) -> bool:
        self._require("can_start_robot")
        if not self._terminal_up:
            return False
        self._robot_running = True
        self._heartbeat_alive = not self._fault_heartbeat
        return True

    def stop_robot(self) -> bool:
        self._require("can_stop_robot")
        self._robot_running = False
        self._heartbeat_alive = False
        return True

    def robot_heartbeat(self) -> bool:
        return self._robot_running and self._heartbeat_alive and not self._fault_heartbeat

    # --- recovery surface ------------------------------------------------
    def terminal_alive(self) -> bool:
        return self._terminal_up

    def account_alive(self) -> bool:
        return self._connected and not self._fault_connection

    def restart_terminal(self) -> bool:
        if self._fault_connection:
            return False
        self._terminal_up = True
        return True

    def reconnect_account(self) -> bool:
        if self._fault_connection:
            self._connected = False
            return False
        self._connected = True
        return True

    # --- simulation harness (§71) ---------------------------------------
    def sim_crash_terminal(self) -> None:
        self._terminal_up = False
        self._robot_running = False
        self._heartbeat_alive = False

    def sim_crash_robot(self) -> None:
        self._robot_running = False
        self._heartbeat_alive = False

    def sim_lose_heartbeat(self) -> None:
        self._fault_heartbeat = True
        self._heartbeat_alive = False

    def sim_restore(self) -> None:
        self._fault_connection = False
        self._fault_heartbeat = False
        self._terminal_up = True

    def sim_set_connection_fault(self, value: bool) -> None:
        self._fault_connection = value

    def sim_tick_pnl(self, delta: float) -> None:
        self._balance += delta
        self._equity = self._balance
