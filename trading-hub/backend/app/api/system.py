"""Events, alerts, settings, attention view, demo + simulation (§55, §63, §71, §74)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..database.base import get_session
from ..database.models import Account, Alert, EventLog, Setting
from ..schemas.models import SeedDemoBody, SimFaultBody
from ..security.credentials import credential_manager
from ..services import recovery_service
from ..services.sessions import sessions
from .serializers import account_row, alert_row, event_row

router = APIRouter(tags=["system"])


@router.get("/events")
def events(limit: int = 100, account_id: int | None = None, session: Session = Depends(get_session)):
    q = session.query(EventLog).order_by(EventLog.id.desc())
    if account_id is not None:
        q = q.filter(EventLog.account_id == account_id)
    return {"events": [event_row(e) for e in q.limit(limit).all()]}


@router.get("/alerts")
def alerts(resolved: bool = False, session: Session = Depends(get_session)):
    q = session.query(Alert).filter(Alert.resolved.is_(resolved)).order_by(Alert.id.desc())
    return {"alerts": [alert_row(a) for a in q.limit(200).all()]}


@router.get("/attention")
def attention(session: Session = Depends(get_session)):
    """§63 : accounts that need a human, with their open alerts."""
    out = []
    for a in session.query(Account).all():
        if a.health in ("attention", "error", "disconnected"):
            open_alerts = [
                alert_row(al) for al in session.query(Alert).filter(
                    Alert.account_id == a.id, Alert.resolved.is_(False)).all()
            ]
            row = account_row(session, a)
            row["alerts"] = open_alerts
            out.append(row)
    return {"accounts": out, "count": len(out)}


@router.get("/settings")
def read_settings(session: Session = Depends(get_session)):
    rows = {s.key: s.value for s in session.query(Setting).all()}
    return {"settings": rows}


@router.put("/settings")
def update_settings(payload: dict[str, str], session: Session = Depends(get_session)):
    for k, v in payload.items():
        row = session.query(Setting).filter(Setting.key == k).one_or_none()
        if row is None:
            row = Setting(key=k, value=str(v))
            session.add(row)
        else:
            row.value = str(v)
    session.commit()
    return {"ok": True}


@router.post("/seed-demo")
def seed_demo(body: SeedDemoBody, session: Session = Depends(get_session)):
    from ..database.seed import seed_demo_accounts, seed_reference
    seed_reference(session)
    created = seed_demo_accounts(session, body.count)
    return {"created": created}


# --- simulation + recovery (§71) ----------------------------------------
@router.post("/sim/{account_id}/fault")
def inject_fault(account_id: int, body: SimFaultBody, session: Session = Depends(get_session)):
    connector = sessions.get(account_id)
    if connector is None or not hasattr(connector, "sim_crash_robot"):
        raise HTTPException(409, "No mock session to fault-inject")
    mapping = {
        "robot": connector.sim_crash_robot,
        "terminal": connector.sim_crash_terminal,
        "heartbeat": connector.sim_lose_heartbeat,
        "restore": connector.sim_restore,
        "connection": lambda: connector.sim_set_connection_fault(True),
    }
    fn = mapping.get(body.fault)
    if fn is None:
        raise HTTPException(400, "Unknown fault")
    fn()
    return {"ok": True, "fault": body.fault, "heartbeat": connector.robot_heartbeat()}


@router.post("/accounts/{account_id}/recover")
def recover(account_id: int, session: Session = Depends(get_session)):
    outcome = recovery_service.run_recovery(session, account_id)
    session.commit()
    if outcome is None:
        raise HTTPException(409, "No live session for this account")
    return {"outcome": outcome.value}


@router.get("/config")
def runtime_config():
    s = get_settings()
    return {
        "mock_mode": s.mock_mode,
        "credential_backend": credential_manager.backend(),
        "confidence_auto": s.confidence_auto,
        "confidence_confirm": s.confidence_confirm,
        "heartbeat_timeout_s": s.heartbeat_timeout_s,
    }
