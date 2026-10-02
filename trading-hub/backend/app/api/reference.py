"""Reference data: prop firms, platforms, strategies, terminals (§46, §57-58, §80)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..connectors import registry
from ..database.base import get_session
from ..database.models import (
    Account,
    MarketMapping,
    Platform,
    PropFirm,
    Strategy,
    TerminalInstance,
)
from .serializers import account_row, prop_firm_row, strategy_row, terminal_row

router = APIRouter(tags=["reference"])


@router.get("/prop-firms")
def prop_firms(session: Session = Depends(get_session)):
    return {"prop_firms": [
        {"id": pf.id, "name": pf.name, "accounts": len(pf.accounts)}
        for pf in session.query(PropFirm).order_by(PropFirm.name).all()
    ]}


@router.get("/prop-firms/{pf_id}")
def prop_firm(pf_id: int, session: Session = Depends(get_session)):
    pf = session.get(PropFirm, pf_id)
    if pf is None:
        raise HTTPException(404, "Prop firm not found")
    data = prop_firm_row(session, pf)
    data["accounts_list"] = [account_row(session, a) for a in pf.accounts]
    return data


@router.get("/platforms")
def platforms(session: Session = Depends(get_session)):
    out = []
    for p in session.query(Platform).order_by(Platform.id).all():
        registered = p.key in registry.available_keys()
        caps: dict = {}
        requirement = ""
        available = False
        cred_fields: list = []
        needs_server = False
        if registered:
            try:
                conn = registry.create(p.key)
                caps = conn.capabilities().as_dict()
                requirement = conn.requirement()
                cred_fields = [f.as_dict() for f in conn.extra_credential_fields()]
                needs_server = conn.needs_server()
                # "available" = can actually operate here (can at least connect).
                available = bool(caps.get("can_connect"))
            except Exception:  # noqa: BLE001
                caps = {}
        out.append({"id": p.id, "key": p.key, "name": p.name,
                    "available": available, "requirement": requirement,
                    "needs_server": needs_server, "credential_fields": cred_fields,
                    "capabilities": caps})
    return {"platforms": out}


@router.get("/strategies")
def strategies(session: Session = Depends(get_session)):
    return {"strategies": [strategy_row(session, s)
                           for s in session.query(Strategy).order_by(Strategy.id).all()]}


@router.get("/terminals")
def terminals(session: Session = Depends(get_session)):
    return {"terminals": [terminal_row(t)
                          for t in session.query(TerminalInstance).order_by(TerminalInstance.id).all()]}


@router.get("/markets")
def markets(session: Session = Depends(get_session)):
    """§58 : universal -> real symbol mapping table across brokers."""
    rows = []
    for m in session.query(MarketMapping).all():
        broker = None
        platform_name = m.platform_key
        rows.append({
            "universal": m.universal_symbol, "real": m.real_symbol,
            "platform": platform_name, "broker": broker,
            "confidence": m.confidence, "status": m.status,
        })
    return {"markets": rows}
