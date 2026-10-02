"""Event log + alert helpers (§50, §55, §68).

Every notable action is recorded to the ``events`` table and broadcast on the
EventBus (so the WebSocket + AlertEngine react). Alerts are the subset that
need user attention. Neither ever contains credentials (§7, §68)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..core.enums import AlertSeverity, AlertType, EventType
from ..core.events import Event, bus
from ..database.base import utcnow
from ..database.models import Alert, EventLog


def record_event(
    session: Session, event_type: EventType, message: str,
    account_id: int | None = None, publish: bool = True, **payload,
) -> EventLog:
    row = EventLog(account_id=account_id, type=event_type.value, message=message, ts=utcnow())
    session.add(row)
    session.flush()
    if publish:
        bus.publish_soon(
            Event(event_type, {"account_id": account_id, "message": message, **payload})
        )
    return row


def raise_alert(
    session: Session, alert_type: AlertType, message: str,
    account_id: int | None = None, severity: AlertSeverity = AlertSeverity.WARNING,
) -> Alert:
    row = Alert(
        account_id=account_id, type=alert_type, severity=severity,
        message=message, resolved=False, ts=utcnow(),
    )
    session.add(row)
    session.flush()
    bus.publish_soon(
        Event(EventType.ALERT_RAISED, {
            "account_id": account_id, "type": alert_type.value,
            "severity": severity.value, "message": message,
        })
    )
    return row


def resolve_alerts(session: Session, account_id: int, alert_type: AlertType | None = None) -> int:
    q = session.query(Alert).filter(Alert.account_id == account_id, Alert.resolved.is_(False))
    if alert_type is not None:
        q = q.filter(Alert.type == alert_type)
    n = 0
    for a in q.all():
        a.resolved = True
        n += 1
    return n
