"""Market resolution service (§24-30).

Ties the discovery (connector) and mapping engine together, persisting results
per account. Priority order is enforced (§89): auto-discovery -> auto-mapping
-> manual confirmation -> manual configuration. A manually validated mapping is
remembered at the (broker, platform) level for reuse (§30) but still re-verified
per account before use."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..connectors.base import PlatformConnector
from ..core.config import get_settings
from ..core.enums import AlertType, EventType, MappingStatus
from ..database.models import AccountMarketMapping, MarketMapping, UniversalMarket
from ..markets.mapping import MarketMappingEngine
from ..markets.universal import DEFAULT_UNIVERSAL, UniversalDef
from .journal import raise_alert, record_event


def _universal_def(session: Session, symbol: str) -> UniversalDef | None:
    for u in DEFAULT_UNIVERSAL:
        if u.symbol == symbol:
            return u
    row = session.query(UniversalMarket).filter(UniversalMarket.symbol == symbol).one_or_none()
    if row:
        from ..core.enums import AssetClass
        return UniversalDef(
            symbol=row.symbol, description=row.description or "",
            asset_class=AssetClass(row.asset_class),
            aliases=[a.strip() for a in (row.aliases or "").split(",") if a.strip()] or [row.symbol],
        )
    return None


def discover_and_map(
    session: Session, connector: PlatformConnector, account_id: int,
    broker_id: int | None, platform_key: str, universal_symbols: list[str],
) -> dict:
    """Resolve each requested universal market to a real symbol for this account."""
    s = get_settings()
    engine = MarketMappingEngine(auto=s.confidence_auto, confirm=s.confidence_confirm)

    if not connector.capabilities().can_discover_markets:
        return {"resolved": [], "unresolved": universal_symbols, "instruments": 0}

    instruments = connector.get_available_markets()
    resolved, unresolved = [], []

    for sym in universal_symbols:
        udef = _universal_def(session, sym)
        if udef is None:
            unresolved.append(sym)
            continue
        best, status = engine.resolve(udef, instruments)
        amm = (
            session.query(AccountMarketMapping)
            .filter(AccountMarketMapping.account_id == account_id,
                    AccountMarketMapping.universal_symbol == sym)
            .one_or_none()
        )
        if amm is None:
            amm = AccountMarketMapping(account_id=account_id, universal_symbol=sym)
            session.add(amm)

        if best and status == MappingStatus.AUTO:
            amm.real_symbol = best.real_symbol
            amm.confidence = best.confidence
            amm.status = MappingStatus.AUTO
            amm.verified = True
            _remember(session, sym, broker_id, platform_key, best.real_symbol, best.confidence, MappingStatus.AUTO)
            resolved.append({"universal": sym, "real": best.real_symbol, "confidence": best.confidence})
            record_event(session, EventType.MARKET_MAPPED,
                         f"{sym} -> {best.real_symbol} ({best.confidence}%)", account_id=account_id)
        else:
            amm.real_symbol = best.real_symbol if best else None
            amm.confidence = best.confidence if best else 0.0
            amm.status = status
            amm.verified = False
            unresolved.append(sym)
            raise_alert(session, AlertType.MARKET_UNRESOLVED,
                        f"Market not resolved: {sym}", account_id=account_id)
            record_event(session, EventType.MARKET_UNRESOLVED,
                         f"{sym} unresolved", account_id=account_id)

    session.flush()
    return {"resolved": resolved, "unresolved": unresolved, "instruments": len(instruments)}


def search_platform(connector: PlatformConnector, universal_symbol: str) -> list[dict]:
    """§28 : return ranked candidate instruments for a manual search."""
    if not connector.capabilities().can_discover_markets:
        return []
    s = get_settings()
    engine = MarketMappingEngine(auto=s.confidence_auto, confirm=s.confidence_confirm)
    udef = None
    for u in DEFAULT_UNIVERSAL:
        if u.symbol == universal_symbol:
            udef = u
            break
    instruments = connector.get_available_markets()
    if udef is None:  # unknown universal: show everything for manual pick
        return [{"real_symbol": i.symbol, "confidence": 0.0, "description": i.description} for i in instruments]
    return [
        {"real_symbol": c.real_symbol, "confidence": c.confidence,
         "description": c.description, "reason": c.reason}
        for c in engine.candidates(udef, instruments)
    ]


def confirm_mapping(
    session: Session, connector: PlatformConnector, account_id: int,
    broker_id: int | None, platform_key: str, universal_symbol: str, real_symbol: str,
) -> dict:
    """§29-30 : user picked a symbol -> verify it exists, persist, remember."""
    exists = connector.get_instrument(real_symbol) is not None
    if not exists:
        return {"ok": False, "reason": f"{real_symbol} not found on this account"}

    amm = (
        session.query(AccountMarketMapping)
        .filter(AccountMarketMapping.account_id == account_id,
                AccountMarketMapping.universal_symbol == universal_symbol)
        .one_or_none()
    )
    if amm is None:
        amm = AccountMarketMapping(account_id=account_id, universal_symbol=universal_symbol)
        session.add(amm)
    amm.real_symbol = real_symbol
    amm.confidence = 100.0
    amm.status = MappingStatus.MANUAL
    amm.verified = True

    _remember(session, universal_symbol, broker_id, platform_key, real_symbol, 100.0, MappingStatus.MANUAL)
    from .journal import resolve_alerts
    resolve_alerts(session, account_id, AlertType.MARKET_UNRESOLVED)
    record_event(session, EventType.MARKET_MAPPED,
                 f"{universal_symbol} -> {real_symbol} (manual)", account_id=account_id)
    session.flush()
    return {"ok": True, "universal": universal_symbol, "real": real_symbol}


def _remember(
    session: Session, universal: str, broker_id: int | None, platform_key: str,
    real_symbol: str, confidence: float, status: MappingStatus,
) -> None:
    mm = (
        session.query(MarketMapping)
        .filter(MarketMapping.universal_symbol == universal,
                MarketMapping.broker_id == broker_id,
                MarketMapping.platform_key == platform_key)
        .one_or_none()
    )
    if mm is None:
        mm = MarketMapping(universal_symbol=universal, broker_id=broker_id, platform_key=platform_key)
        session.add(mm)
    mm.real_symbol = real_symbol
    mm.confidence = confidence
    mm.status = status
