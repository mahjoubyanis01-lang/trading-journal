"""MetaTrader file-bridge protocol tests (§21, §66)."""
import time
from datetime import datetime, timezone

import pytest

from app.terminal import bridge


def test_config_roundtrip(tmp_path):
    bridge.write_config(tmp_path, risk_mode="fixed_money", risk_amount=50.0,
                        markets=["EURUSDm", "USTEC"], magic=12345)
    import json
    data = json.loads((bridge.bridge_dir(tmp_path) / "config.json").read_text())
    assert data["risk_mode"] == "fixed_money"
    assert data["risk_amount"] == 50.0
    assert data["markets"] == ["EURUSDm", "USTEC"]
    assert data["magic"] == 12345
    assert data["enabled"] is True


def test_command_validation(tmp_path):
    p = bridge.write_command(tmp_path, "run")
    assert p.read_text() == "RUN"
    bridge.write_command(tmp_path, "STOP")
    with pytest.raises(ValueError):
        bridge.write_command(tmp_path, "PAUSE")


def test_preset_written_as_key_values(tmp_path):
    p = bridge.write_preset(tmp_path, "StrategyA",
                            {"RiskMode": "fixed_money", "RiskAmount": 75.0, "Enabled": True})
    text = p.read_text()
    assert "RiskAmount=75.0" in text
    assert "Enabled=true" in text
    assert p.name == "StrategyA.set"


def test_heartbeat_fresh_and_stale(tmp_path):
    hb = bridge.bridge_dir(tmp_path) / "heartbeat.txt"
    hb.write_text(str(int(time.time())))
    assert bridge.heartbeat_fresh(tmp_path, timeout_s=60)
    # stale
    hb.write_text(str(int(time.time()) - 600))
    assert not bridge.heartbeat_fresh(tmp_path, timeout_s=60)
    # missing
    hb.unlink()
    assert not bridge.heartbeat_fresh(tmp_path, timeout_s=60)
    assert bridge.read_heartbeat(tmp_path) is None


def test_read_account(tmp_path):
    (bridge.bridge_dir(tmp_path) / "account.json").write_text(
        '{"login":123,"balance":10842.0,"equity":10795.0,"currency":"USD","positions":[]}'
    )
    acc = bridge.read_account(tmp_path)
    assert acc["balance"] == 10842.0
    assert acc["positions"] == []


def test_heartbeat_uses_utc(tmp_path):
    now = datetime.now(timezone.utc)
    (bridge.bridge_dir(tmp_path) / "heartbeat.txt").write_text(str(int(now.timestamp())))
    hb = bridge.read_heartbeat(tmp_path)
    assert hb is not None and hb.tzinfo is not None
