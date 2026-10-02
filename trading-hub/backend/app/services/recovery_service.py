"""Recovery service - wires the RecoveryEngine to a live account (§51-52)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.enums import (
    AlertSeverity,
    AlertType,
    EventType,
    HealthStatus,
    RecoveryState,
    RobotStatus,
)
from ..database.base import utcnow
from ..database.models import Account, RobotInstance
from ..recovery.engine import RecoveryEngine
from .journal import raise_alert, record_event, resolve_alerts
from .sessions import sessions


def run_recovery(session: Session, account_id: int) -> RecoveryState | None:
    connector = sessions.get(account_id)
    if connector is None:
        return None
    account = session.get(Account, account_id)
    ri = session.query(RobotInstance).filter(RobotInstance.account_id == account_id).one_or_none()

    record_event(session, EventType.RECOVERY_STARTED, "Auto-recovery started", account_id=account_id)
    report = RecoveryEngine(max_attempts=get_settings().recovery_max_attempts).run(connector)

    if report.outcome == RecoveryState.RECOVERED:
        if ri:
            ri.status = RobotStatus.ACTIVE
            ri.last_heartbeat = utcnow()
            ri.last_error = None
        if account:
            account.health = HealthStatus.OPERATIONAL
        resolve_alerts(session, account_id, AlertType.ROBOT_HEARTBEAT_LOST)
        resolve_alerts(session, account_id, AlertType.TERMINAL_CLOSED)
        record_event(session, EventType.RECOVERY_SUCCEEDED,
                     f"Robot recovered in {report.attempts} attempt(s)", account_id=account_id)
    else:
        if ri:
            ri.status = RobotStatus.ERROR
            ri.last_error = report.detail
        if account:
            account.health = HealthStatus.ERROR
        raise_alert(session, AlertType.RECOVERY_FAILED, report.detail,
                    account_id=account_id, severity=AlertSeverity.CRITICAL)
        record_event(session, EventType.RECOVERY_FAILED, report.detail, account_id=account_id)

    session.flush()
    return report.outcome
