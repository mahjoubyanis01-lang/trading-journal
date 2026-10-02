"""Serializers: ORM -> plain dicts for the API. No credential ever included (§7)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..core.enums import RiskMode, RiskReference
from ..database.models import (
    Account,
    AccountMarketMapping,
    Alert,
    EventLog,
    PropFirm,
    RobotInstance,
    Strategy,
    TerminalInstance,
)
from ..performance import engine as perf
from ..risk.engine import resolve_effective_risk


def effective_risk(account: Account, strategy: Strategy | None):
    if strategy is None:
        return None
    return resolve_effective_risk(
        account_mode=account.risk_mode, account_amount=account.risk_amount,
        account_percent=account.risk_percent, account_reference=account.risk_reference,
        strategy_mode=RiskMode(strategy.default_risk_mode),
        strategy_percent=strategy.default_risk_percent,
        strategy_reference=RiskReference(strategy.default_risk_reference),
        initial_balance=account.initial_balance, current_balance=account.balance,
        equity=account.equity,
    )


def account_row(session: Session, a: Account) -> dict:
    strat = a.strategy
    risk = effective_risk(a, strat)
    ri: RobotInstance | None = a.robot
    return {
        "id": a.id,
        "name": a.name,
        "prop_firm": a.prop_firm.name if a.prop_firm else None,
        "prop_firm_id": a.prop_firm_id,
        "platform": a.platform.name if a.platform else None,
        "platform_key": a.platform.key if a.platform else None,
        "server": a.broker.server if a.broker else None,
        "strategy": strat.name if strat else None,
        "robot_version": ri.robot_version if ri else None,
        "capital": a.initial_balance,
        "balance": a.balance,
        "equity": a.equity,
        "currency": a.currency,
        "pnl_total": perf.total_pnl(a.initial_balance, a.balance),
        "performance_pct": perf.performance_pct(a.initial_balance, a.balance),
        "risk_mode": risk.mode.value if risk else None,
        "risk_amount": risk.amount if risk else None,
        "risk_source": risk.source if risk else None,
        "robot_status": ri.status if ri else "unknown",
        "terminal": a.terminal.instance_id if a.terminal else None,
        "health": a.health,
        "connection": a.connection,
    }


def pnl_today(session: Session, account_id: int) -> float:
    from datetime import date

    from ..database.models import DailyPerformance
    row = (
        session.query(DailyPerformance)
        .filter(DailyPerformance.account_id == account_id, DailyPerformance.day == date.today())
        .one_or_none()
    )
    return row.pnl if row else 0.0


def pnl_month(session: Session, account_id: int) -> float:
    from datetime import date

    from ..database.models import DailyPerformance
    today = date.today()
    rows = (
        session.query(DailyPerformance)
        .filter(DailyPerformance.account_id == account_id,
                DailyPerformance.day >= today.replace(day=1))
        .all()
    )
    return perf.sum_pnl([r.pnl for r in rows])


def account_detail(session: Session, a: Account) -> dict:
    base = account_row(session, a)
    mappings = (
        session.query(AccountMarketMapping)
        .filter(AccountMarketMapping.account_id == a.id)
        .all()
    )
    risk = effective_risk(a, a.strategy)
    base.update({
        "pnl_today": pnl_today(session, a.id),
        "pnl_month": pnl_month(session, a.id),
        "risk_reference": risk.reference.value if risk else None,
        "risk_reference_value": risk.reference_value if risk else None,
        "risk_percent": risk.percent if risk else None,
        "heartbeat": "ok" if (a.robot and a.robot.last_heartbeat) else "unknown",
        "markets": [
            {"universal": m.universal_symbol, "real": m.real_symbol,
             "confidence": m.confidence, "status": m.status, "verified": m.verified}
            for m in mappings
        ],
        "terminal_detail": terminal_row(a.terminal) if a.terminal else None,
    })
    return base


def terminal_row(t: TerminalInstance) -> dict:
    return {
        "instance_id": t.instance_id, "account_id": t.account_id,
        "platform_key": t.platform_key, "status": t.status,
        "process_id": t.process_id, "terminal_path": t.terminal_path,
    }


def prop_firm_row(session: Session, pf: PropFirm) -> dict:
    accounts = pf.accounts
    capital = perf.aggregate_capital([a.initial_balance for a in accounts])
    pnl_t = sum(pnl_today(session, a.id) for a in accounts)
    pnl_m = sum(pnl_month(session, a.id) for a in accounts)
    total_pnl = sum(perf.total_pnl(a.initial_balance, a.balance) for a in accounts)
    robots_active = sum(1 for a in accounts if a.robot and a.robot.status == "active")
    return {
        "id": pf.id, "name": pf.name, "accounts": len(accounts),
        "capital": capital, "pnl_today": round(pnl_t, 2), "pnl_month": round(pnl_m, 2),
        "performance_pct": perf.monthly_performance_pct(capital, total_pnl) if capital else 0.0,
        "robots_active": robots_active,
    }


def strategy_row(session: Session, s: Strategy) -> dict:
    accounts = s.accounts
    active = sum(1 for a in accounts if a.robot and a.robot.status == "active")
    from ..services.strategy_manager import current_robot_version
    return {
        "id": s.id, "name": s.name, "enabled": s.enabled,
        "accounts": len(accounts), "active": active,
        "attention": sum(1 for a in accounts if a.health == "attention"),
        "markets": s.market_list(),
        "risk_percent": s.default_risk_percent,
        "version": current_robot_version(session, s.id),
    }


def alert_row(a: Alert) -> dict:
    return {"id": a.id, "account_id": a.account_id, "type": a.type,
            "severity": a.severity, "message": a.message, "resolved": a.resolved,
            "ts": a.ts.isoformat()}


def event_row(e: EventLog) -> dict:
    return {"id": e.id, "account_id": e.account_id, "type": e.type,
            "message": e.message, "ts": e.ts.isoformat()}
