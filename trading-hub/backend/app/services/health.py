"""Account health + configuration inheritance (§59, §67).

Health is derived from the component states (§67). Precedence, worst wins:
DISCONNECTED > ERROR > ATTENTION > OPERATIONAL. Pure function => unit-testable."""
from __future__ import annotations

from dataclasses import dataclass

from ..core.enums import (
    ConnectionStatus,
    HealthStatus,
    RiskMode,
    RiskReference,
    RobotStatus,
    TerminalStatus,
)


@dataclass(slots=True)
class HealthSignals:
    connection: ConnectionStatus
    terminal: TerminalStatus
    robot: RobotStatus
    heartbeat_ok: bool
    has_unresolved_market: bool = False
    risk_ok: bool = True
    version_mismatch: bool = False
    template_mismatch: bool = False
    drawdown_warning: bool = False


def compute_health(s: HealthSignals) -> HealthStatus:
    if s.connection == ConnectionStatus.DISCONNECTED:
        return HealthStatus.DISCONNECTED

    error = (
        s.robot == RobotStatus.ERROR
        or s.terminal == TerminalStatus.CRASHED
        or not s.risk_ok
        or (s.robot == RobotStatus.ACTIVE and not s.heartbeat_ok)
    )
    if error:
        return HealthStatus.ERROR

    attention = (
        s.has_unresolved_market
        or s.version_mismatch
        or s.template_mismatch
        or s.drawdown_warning
    )
    if attention:
        return HealthStatus.ATTENTION

    return HealthStatus.OPERATIONAL


# --- configuration inheritance (§59, §91) -------------------------------
@dataclass(slots=True)
class ResolvedConfig:
    risk_mode: RiskMode
    risk_percent: float
    risk_reference: RiskReference
    auto_start: bool
    auto_recovery: bool
    template_name: str
    markets: list[str]
    risk_source: str  # "inherited" | "override"
    auto_start_source: str
    auto_recovery_source: str
    template_source: str


def resolve_config(account, strategy) -> ResolvedConfig:
    """Account values override strategy values; otherwise inherit (§59)."""
    def pick(acc_val, strat_val):
        return (acc_val, "override") if acc_val is not None else (strat_val, "inherited")

    rm, risk_src = pick(account.risk_mode, strategy.default_risk_mode)
    rp = account.risk_percent if account.risk_percent is not None else strategy.default_risk_percent
    rr = account.risk_reference or strategy.default_risk_reference
    a_s, a_s_src = pick(account.auto_start, strategy.auto_start)
    a_r, a_r_src = pick(account.auto_recovery, strategy.auto_recovery)
    tpl, tpl_src = pick(account.template_name, strategy.template_name)

    return ResolvedConfig(
        risk_mode=rm, risk_percent=rp, risk_reference=rr,
        auto_start=a_s, auto_recovery=a_r, template_name=tpl,
        markets=strategy.market_list(),
        risk_source="override" if account.risk_mode is not None or account.risk_amount is not None else "inherited",
        auto_start_source=a_s_src, auto_recovery_source=a_r_src, template_source=tpl_src,
    )
