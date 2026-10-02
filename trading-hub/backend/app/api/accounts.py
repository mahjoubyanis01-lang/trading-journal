"""Accounts, robot control, markets, risk (§61-62, §80)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.enums import AlertType, EventType, RiskMode
from ..database.base import get_session
from ..database.models import Account, RobotInstance, Strategy
from ..risk.engine import check_risk_guard
from ..robots.manager import robot_manager
from ..schemas.models import (
    AddAccountBody,
    MarketConfirmBody,
    MarketSearchBody,
    MassActionBody,
    MassRiskBody,
    RiskUpdateBody,
)
from ..services import account_manager, market_service
from ..services.journal import record_event, resolve_alerts
from ..services.sessions import sessions
from .serializers import account_detail, account_row

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _account(session: Session, account_id: int) -> Account:
    a = session.get(Account, account_id)
    if a is None:
        raise HTTPException(404, "Account not found")
    return a


@router.get("")
def list_accounts(
    session: Session = Depends(get_session),
    prop_firm: str | None = None,
    platform: str | None = None,
    status: str | None = None,
    q: str | None = None,
):
    accounts = session.query(Account).order_by(Account.id).all()
    rows = [account_row(session, a) for a in accounts]
    if prop_firm:
        rows = [r for r in rows if r["prop_firm"] == prop_firm]
    if platform:
        rows = [r for r in rows if r["platform_key"] == platform]
    if status:
        rows = [r for r in rows if r["health"] == status]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in (r["name"] or "").lower()
                or ql in (r["prop_firm"] or "").lower()]
    return {"accounts": rows, "total": len(rows)}


@router.post("", status_code=201)
def add_account(body: AddAccountBody, session: Session = Depends(get_session)):
    try:
        account, steps = account_manager.add_account(
            session, account_manager.AddAccountInput(**body.model_dump())
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    session.commit()
    return {"account": account_detail(session, account),
            "steps": [{"name": s.name, "ok": s.ok, "detail": s.detail} for s in steps]}


@router.get("/{account_id}")
def get_account(account_id: int, session: Session = Depends(get_session)):
    return account_detail(session, _account(session, account_id))


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int, session: Session = Depends(get_session)):
    account_manager.remove_account(session, account_id)
    session.commit()


# --- robot control ------------------------------------------------------
@router.post("/{account_id}/robot/{action}")
def robot_action(account_id: int, action: str, session: Session = Depends(get_session)):
    a = _account(session, account_id)
    connector = sessions.get(account_id)
    ri = session.query(RobotInstance).filter(RobotInstance.account_id == account_id).one_or_none()
    if connector is None or ri is None:
        raise HTTPException(409, "Account has no live session")
    if action == "start":
        robot_manager.start(session, connector, ri)
    elif action == "stop":
        robot_manager.stop(session, connector, ri)
    elif action == "restart":
        robot_manager.restart(session, connector, ri)
    else:
        raise HTTPException(400, "Unknown action")
    session.commit()
    return account_detail(session, a)


# --- markets ------------------------------------------------------------
@router.post("/{account_id}/markets/discover")
def discover_markets(account_id: int, session: Session = Depends(get_session)):
    a = _account(session, account_id)
    connector = sessions.get(account_id)
    if connector is None:
        raise HTTPException(409, "Account has no live session")
    strat = a.strategy
    result = market_service.discover_and_map(
        session, connector, account_id, a.broker_id, a.platform.key,
        strat.market_list() if strat else [],
    )
    session.commit()
    return result


@router.post("/{account_id}/markets/search")
def search_markets(account_id: int, body: MarketSearchBody, session: Session = Depends(get_session)):
    _account(session, account_id)
    connector = sessions.get(account_id)
    if connector is None:
        raise HTTPException(409, "Account has no live session")
    return {"candidates": market_service.search_platform(connector, body.universal_symbol)}


@router.post("/{account_id}/markets/map")
def map_market(account_id: int, body: MarketConfirmBody, session: Session = Depends(get_session)):
    a = _account(session, account_id)
    connector = sessions.get(account_id)
    if connector is None:
        raise HTTPException(409, "Account has no live session")
    res = market_service.confirm_mapping(
        session, connector, account_id, a.broker_id, a.platform.key,
        body.universal_symbol, body.real_symbol,
    )
    if not res.get("ok"):
        session.commit()
        raise HTTPException(409, res.get("reason", "mapping failed"))
    # re-configure + ensure robot running with the new symbol (§29)
    ri = a.robot
    if ri and connector.capabilities().can_configure_robot:
        from ..connectors.base import RobotConfig
        from .serializers import effective_risk
        risk = effective_risk(a, a.strategy)
        reals = [m.real_symbol for m in a_market_mappings(session, account_id) if m.real_symbol]
        connector.configure_robot(RobotConfig(
            risk_mode=risk.mode.value if risk else "fixed_money",
            risk_amount=risk.amount if risk else 0.0, markets=reals))
        robot_manager.restart(session, connector, ri)
    # recompute health now the market is resolved
    from ..services.health import HealthSignals, compute_health
    from ..core.enums import TerminalStatus
    unresolved = any(not m.verified for m in a_market_mappings(session, account_id))
    a.health = compute_health(HealthSignals(
        connection=a.connection,
        terminal=a.terminal.status if a.terminal else TerminalStatus.STOPPED,
        robot=ri.status if ri else "unknown", heartbeat_ok=connector.robot_heartbeat(),
        has_unresolved_market=unresolved,
    ))
    session.commit()
    return account_detail(session, a)


def a_market_mappings(session: Session, account_id: int):
    from ..database.models import AccountMarketMapping
    return session.query(AccountMarketMapping).filter(
        AccountMarketMapping.account_id == account_id).all()


# --- risk ---------------------------------------------------------------
@router.post("/{account_id}/risk")
def update_risk(account_id: int, body: RiskUpdateBody, session: Session = Depends(get_session)):
    a = _account(session, account_id)
    s = get_settings()
    # Hard safety cap: refuse an obviously dangerous risk outright (§39, safety).
    if s.risk_hard_fraction > 0 and a.initial_balance > 0 and (
        body.amount / a.initial_balance >= s.risk_hard_fraction
    ):
        raise HTTPException(
            400,
            f"Risk {body.amount} exceeds the hard cap of "
            f"{round(s.risk_hard_fraction * 100)}% of capital",
        )
    guard = check_risk_guard(body.amount, a.initial_balance, s.risk_warn_fraction)
    if not guard.allowed:
        raise HTTPException(400, "; ".join(guard.warnings))
    if guard.needs_confirmation and not body.confirm:
        return {"needs_confirmation": True, "warnings": guard.warnings,
                "old_amount": a.risk_amount, "new_amount": body.amount}
    old = a.risk_amount
    a.risk_mode = body.mode
    a.risk_amount = body.amount
    connector = sessions.get(account_id)
    if connector and connector.capabilities().can_configure_robot:
        from ..connectors.base import RobotConfig
        reals = [m.real_symbol for m in a_market_mappings(session, account_id) if m.real_symbol]
        ok = connector.configure_robot(RobotConfig(body.mode.value, body.amount, reals))
        if not ok:
            session.rollback()
            raise HTTPException(409, "Robot configuration failed")
    record_event(session, EventType.RISK_CHANGED,
                 f"Risk {old} -> {body.amount} {a.currency}", account_id=account_id)
    resolve_alerts(session, account_id, AlertType.RISK_CONFIGURATION_FAILED)
    session.commit()
    return account_detail(session, a)


@router.post("/risk/mass")
def mass_risk(body: MassRiskBody, session: Session = Depends(get_session)):
    ids = set(body.account_ids)
    if body.strategy_id:
        ids |= {a.id for a in session.query(Account).filter(Account.strategy_id == body.strategy_id)}
    accounts = [session.get(Account, i) for i in ids if session.get(Account, i)]
    if not body.confirm:
        return {"needs_confirmation": True, "affected": len(accounts),
                "message": f"{len(accounts)} comptes seront modifiés."}
    for a in accounts:
        a.risk_mode = body.mode
        a.risk_amount = body.amount
        connector = sessions.get(a.id)
        if connector and connector.capabilities().can_configure_robot:
            from ..connectors.base import RobotConfig
            reals = [m.real_symbol for m in a_market_mappings(session, a.id) if m.real_symbol]
            connector.configure_robot(RobotConfig(body.mode.value, body.amount, reals))
        record_event(session, EventType.RISK_CHANGED,
                     f"Risk -> {body.amount} (mass)", account_id=a.id, publish=False)
    session.commit()
    return {"applied": len(accounts)}


# --- mass action --------------------------------------------------------
@router.post("/stop-all")
def stop_all(session: Session = Depends(get_session)):
    """Safety kill-switch: stop every running robot immediately (§52 keeps
    positions open - this halts new activity, it does not liquidate)."""
    stopped = 0
    for ri in session.query(RobotInstance).all():
        connector = sessions.get(ri.account_id)
        if connector is None or not connector.capabilities().can_stop_robot:
            continue
        if robot_manager.stop(session, connector, ri):
            stopped += 1
    record_event(session, EventType.ROBOT_STOPPED, f"PANIC STOP: {stopped} robots stopped")
    session.commit()
    return {"stopped": stopped}


@router.post("/mass-action")
def mass_action(body: MassActionBody, session: Session = Depends(get_session)):
    done = 0
    for aid in body.account_ids:
        connector = sessions.get(aid)
        ri = session.query(RobotInstance).filter(RobotInstance.account_id == aid).one_or_none()
        if connector is None or ri is None:
            continue
        if body.action == "start":
            robot_manager.start(session, connector, ri)
        elif body.action == "stop":
            robot_manager.stop(session, connector, ri)
        elif body.action == "restart":
            robot_manager.restart(session, connector, ri)
        done += 1
    session.commit()
    return {"applied": done, "action": body.action}
