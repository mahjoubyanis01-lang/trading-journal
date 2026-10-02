"""What of the MT5 connector can be proven WITHOUT Windows/MetaTrader.

The Windows-only bits (finding the install, launching terminal64.exe,
mt5.initialize/login, EA compilation) genuinely cannot run here. But the
*control plane* the connector uses to drive a running terminal is the
OS-independent file bridge — and that we can verify end to end:
  - configure_robot writes config.json (+ the EA .set preset),
  - start_robot / stop_robot write RUN / STOP commands,
  - robot_heartbeat reads the heartbeat file the EA writes.
"""
from __future__ import annotations

import json
import time

from app.terminal import bridge, mt5_agent
from app.connectors.base import RobotConfig
from app.connectors.mt5.mt5 import MT5Connector


def _armed_connector(tmp_path, monkeypatch) -> MT5Connector:
    # Pretend the MT5 runtime is present so capabilities() is enabled, and
    # point the connector at a temp "instance" directory.
    monkeypatch.setattr(MT5Connector, "runtime_available", staticmethod(lambda: True))
    c = MT5Connector()
    c._instance = mt5_agent.InstancePaths(
        instance_id="MT5-001", root=tmp_path,
        terminal_exe=tmp_path / "terminal64.exe", data_path=tmp_path,
    )
    c._pid = 4321
    c._robot_installed = True
    return c


def test_configure_writes_bridge_config_and_preset(tmp_path, monkeypatch):
    c = _armed_connector(tmp_path, monkeypatch)
    ok = c.configure_robot(RobotConfig(risk_mode="fixed_money", risk_amount=50.0,
                                       markets=["EURUSDm", "USTEC"]))
    assert ok
    cfg = json.loads((bridge.bridge_dir(tmp_path) / "config.json").read_text())
    assert cfg["risk_amount"] == 50.0 and cfg["markets"] == ["EURUSDm", "USTEC"]
    preset = (tmp_path / "MQL5" / "Presets" / "StrategyA.set").read_text()
    assert "RiskAmount=50.0" in preset


def test_start_stop_write_commands(tmp_path, monkeypatch):
    c = _armed_connector(tmp_path, monkeypatch)
    c.start_robot()
    assert (bridge.bridge_dir(tmp_path) / "command.txt").read_text() == "RUN"
    c.stop_robot()
    assert (bridge.bridge_dir(tmp_path) / "command.txt").read_text() == "STOP"


def test_heartbeat_reads_bridge_file(tmp_path, monkeypatch):
    c = _armed_connector(tmp_path, monkeypatch)
    # No heartbeat file yet, and pid liveness is false on Linux → not alive.
    assert c.robot_heartbeat() is False
    # EA writes a fresh heartbeat → connector reports alive.
    (bridge.bridge_dir(tmp_path) / "heartbeat.txt").write_text(str(int(time.time())))
    assert c.robot_heartbeat() is True
