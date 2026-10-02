"""Strategy helpers (§19, §57)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..database.models import RobotVersion, Strategy


def get_default_strategy(session: Session) -> Strategy | None:
    return session.query(Strategy).order_by(Strategy.id).first()


def current_robot_version(session: Session, strategy_id: int) -> str | None:
    rv = (
        session.query(RobotVersion)
        .filter(RobotVersion.strategy_id == strategy_id, RobotVersion.is_current.is_(True))
        .one_or_none()
    )
    if rv:
        return rv.version
    rv = (
        session.query(RobotVersion)
        .filter(RobotVersion.strategy_id == strategy_id)
        .order_by(RobotVersion.id.desc())
        .first()
    )
    return rv.version if rv else None


def robot_file(session: Session, strategy_id: int, version: str | None) -> str | None:
    q = session.query(RobotVersion).filter(RobotVersion.strategy_id == strategy_id)
    if version:
        q = q.filter(RobotVersion.version == version)
    rv = q.first()
    return rv.robot_file if rv else None
