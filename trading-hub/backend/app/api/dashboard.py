"""Global dashboard aggregation (§40-41, §82)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database.base import get_session
from ..database.models import Account, EventLog, PropFirm
from ..performance import engine as perf
from .serializers import account_row, event_row, pnl_month, pnl_today, prop_firm_row

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(session: Session = Depends(get_session)):
    accounts = session.query(Account).all()
    capital = perf.aggregate_capital([a.initial_balance for a in accounts])
    balance_total = round(sum(a.balance for a in accounts), 2)
    equity_total = round(sum(a.equity for a in accounts), 2)
    pnl_t = round(sum(pnl_today(session, a.id) for a in accounts), 2)
    pnl_m = round(sum(pnl_month(session, a.id) for a in accounts), 2)
    total_pnl = round(sum(perf.total_pnl(a.initial_balance, a.balance) for a in accounts), 2)
    robots_total = sum(1 for a in accounts if a.robot)
    robots_active = sum(1 for a in accounts if a.robot and a.robot.status == "active")

    by_health: dict[str, int] = {}
    for a in accounts:
        by_health[a.health] = by_health.get(a.health, 0) + 1

    global_dd = round(max(0.0, capital - equity_total) / capital * 100, 2) if capital else 0.0

    firms = [prop_firm_row(session, pf) for pf in session.query(PropFirm).all()]
    firms = [f for f in firms if f["accounts"] > 0]
    firms.sort(key=lambda f: f["capital"], reverse=True)

    attention = [
        account_row(session, a) for a in accounts
        if a.health in ("attention", "error", "disconnected")
    ]
    recent = (
        session.query(EventLog).order_by(EventLog.id.desc()).limit(15).all()
    )

    return {
        "accounts": len(accounts),
        "capital": capital,
        "balance_total": balance_total,
        "equity_total": equity_total,
        "pnl_today": pnl_t,
        "pnl_month": pnl_m,
        "performance_pct": perf.monthly_performance_pct(capital, total_pnl) if capital else 0.0,
        "drawdown_global": global_dd,
        "robots_active": robots_active,
        "robots_total": robots_total,
        "by_health": by_health,
        "prop_firms": firms,
        "attention": attention,
        "recent_events": [event_row(e) for e in recent],
    }
