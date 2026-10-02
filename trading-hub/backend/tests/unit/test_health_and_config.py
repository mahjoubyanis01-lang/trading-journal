"""Account health + configuration inheritance tests (§59, §67)."""
from types import SimpleNamespace

from app.core.enums import (
    ConnectionStatus,
    HealthStatus,
    RiskMode,
    RiskReference,
    RobotStatus,
    TerminalStatus,
)
from app.services.health import HealthSignals, compute_health, resolve_config


def _signals(**kw):
    base = dict(
        connection=ConnectionStatus.CONNECTED, terminal=TerminalStatus.RUNNING,
        robot=RobotStatus.ACTIVE, heartbeat_ok=True,
    )
    base.update(kw)
    return HealthSignals(**base)


def test_operational_when_all_good():
    assert compute_health(_signals()) == HealthStatus.OPERATIONAL


def test_disconnected_wins():
    assert compute_health(_signals(connection=ConnectionStatus.DISCONNECTED)) == HealthStatus.DISCONNECTED


def test_heartbeat_lost_is_error():
    assert compute_health(_signals(heartbeat_ok=False)) == HealthStatus.ERROR


def test_unresolved_market_is_attention():
    assert compute_health(_signals(has_unresolved_market=True)) == HealthStatus.ATTENTION


def test_version_mismatch_is_attention():
    assert compute_health(_signals(version_mismatch=True)) == HealthStatus.ATTENTION


# --- configuration inheritance (§59) ---
def _strategy():
    return SimpleNamespace(
        default_risk_mode=RiskMode.FIXED_MONEY, default_risk_percent=0.5,
        default_risk_reference=RiskReference.INITIAL_BALANCE,
        auto_start=True, auto_recovery=True, template_name="Default MT5",
        market_list=lambda: ["EURUSD", "XAUUSD"],
    )


def _account(**kw):
    base = dict(
        risk_mode=None, risk_amount=None, risk_percent=None, risk_reference=None,
        auto_start=None, auto_recovery=None, template_name=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_config_inherited_by_default():
    cfg = resolve_config(_account(), _strategy())
    assert cfg.risk_source == "inherited"
    assert cfg.template_name == "Default MT5"
    assert cfg.markets == ["EURUSD", "XAUUSD"]


def test_config_override_is_explicit():
    cfg = resolve_config(_account(risk_mode=RiskMode.FIXED_MONEY, risk_amount=75), _strategy())
    assert cfg.risk_source == "override"


def test_template_override():
    cfg = resolve_config(_account(template_name="Custom"), _strategy())
    assert cfg.template_name == "Custom"
    assert cfg.template_source == "override"
