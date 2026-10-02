"""Background monitor loop (§64, §66, §72).

Periodically (not per-millisecond) polls each live account's heartbeat,
derives robot/health status, and triggers auto-recovery when enabled. Designed
to stay cheap at 100+ accounts: one short pass per interval, one DB session per
pass, only changed rows touched (§72-73). The main UI never blocks on it."""
from __future__ import annotations

import asyncio
import logging

from ..core.config import get_settings
from ..core.enums import RobotStatus, TerminalStatus
from ..database.base import SessionLocal
from ..database.models import Account, RobotInstance
from .health import HealthSignals, compute_health
from .recovery_service import run_recovery
from .sessions import sessions

log = logging.getLogger("trading_hub.monitor")


async def monitor_once() -> None:
    s = get_settings()
    live = sessions.all()
    if not live:
        return
    session = SessionLocal()
    try:
        for account_id, connector in live.items():
            account = session.get(Account, account_id)
            ri = session.query(RobotInstance).filter(RobotInstance.account_id == account_id).one_or_none()
            if account is None or ri is None:
                continue
            heartbeat_ok = connector.robot_heartbeat()
            if not heartbeat_ok and ri.status == RobotStatus.ACTIVE:
                ri.status = RobotStatus.ERROR
                session.commit()
                auto_recovery = account.auto_recovery
                if auto_recovery is None and account.strategy is not None:
                    auto_recovery = account.strategy.auto_recovery
                if s.auto_recovery and auto_recovery:
                    run_recovery(session, account_id)
                    session.commit()
            # refresh health
            term_status = account.terminal.status if account.terminal else TerminalStatus.STOPPED
            account.health = compute_health(HealthSignals(
                connection=account.connection, terminal=term_status,
                robot=ri.status, heartbeat_ok=connector.robot_heartbeat(),
            ))
        session.commit()
    except Exception:  # noqa: BLE001 - monitor must never crash the app
        log.exception("monitor pass failed")
        session.rollback()
    finally:
        session.close()


async def monitor_loop(stop_event: asyncio.Event) -> None:
    interval = get_settings().monitor_interval_s
    while not stop_event.is_set():
        await monitor_once()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
