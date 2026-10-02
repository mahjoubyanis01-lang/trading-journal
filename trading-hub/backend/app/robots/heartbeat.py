"""Heartbeat evaluation (§66).

Pure helper: decide whether a robot is alive given its last heartbeat and a
configurable timeout. Kept separate so it is unit-testable without any clock
or platform dependency."""
from __future__ import annotations

from datetime import datetime, timezone

from ..core.enums import RobotStatus


def is_alive(last_heartbeat: datetime | None, now: datetime, timeout_s: int) -> bool:
    if last_heartbeat is None:
        return False
    if last_heartbeat.tzinfo is None:
        last_heartbeat = last_heartbeat.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return (now - last_heartbeat).total_seconds() <= timeout_s


def derive_status(
    current: RobotStatus, last_heartbeat: datetime | None, now: datetime, timeout_s: int
) -> RobotStatus:
    """A robot marked ACTIVE but silent past the timeout becomes ERROR (lost)."""
    if current in (RobotStatus.STARTING, RobotStatus.STOPPING, RobotStatus.STOPPED):
        return current
    if current == RobotStatus.ACTIVE and not is_alive(last_heartbeat, now, timeout_s):
        return RobotStatus.ERROR
    return current
