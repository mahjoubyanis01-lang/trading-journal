"""Robot manager (§19-22, §53).

Owns a RobotInstance per account: install, configure, start, stop, restart,
heartbeat. Each instance runs independently - there is NO master/slave, no
position copying (§2). Robot actions always flow through the connector so an
unsupported platform cannot be asked to do the impossible (§9)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..connectors.base import PlatformConnector, RobotConfig
from ..core.enums import AlertType, EventType, RobotStatus
from ..database.base import utcnow
from ..database.models import RobotInstance
from ..services.journal import raise_alert, record_event, resolve_alerts


class RobotManager:
    def ensure_instance(
        self, session: Session, account_id: int, strategy_id: int | None,
        robot_version: str | None, terminal_instance_id: str | None,
    ) -> RobotInstance:
        ri = (
            session.query(RobotInstance)
            .filter(RobotInstance.account_id == account_id)
            .one_or_none()
        )
        if ri is None:
            ri = RobotInstance(account_id=account_id)
            session.add(ri)
        ri.strategy_id = strategy_id
        ri.robot_version = robot_version
        ri.terminal_instance_id = terminal_instance_id
        session.flush()
        return ri

    def install_and_configure(
        self, connector: PlatformConnector, robot_file: str | None, config: RobotConfig
    ) -> bool:
        caps = connector.capabilities()
        if caps.can_install_robot:
            connector.install_robot(robot_file)
        if caps.can_configure_robot:
            return connector.configure_robot(config)
        return False

    def start(self, session: Session, connector: PlatformConnector, ri: RobotInstance) -> bool:
        if not connector.capabilities().can_start_robot:
            ri.status = RobotStatus.UNKNOWN
            return False
        ri.status = RobotStatus.STARTING
        ok = connector.start_robot()
        if ok:
            ri.status = RobotStatus.ACTIVE
            ri.last_start = utcnow()
            ri.last_heartbeat = utcnow()
            resolve_alerts(session, ri.account_id, AlertType.ROBOT_STOPPED)
            record_event(session, EventType.ROBOT_STARTED, "Robot started",
                         account_id=ri.account_id)
        else:
            ri.status = RobotStatus.ERROR
            ri.last_error = "start failed"
        return ok

    def stop(self, session: Session, connector: PlatformConnector, ri: RobotInstance) -> bool:
        if not connector.capabilities().can_stop_robot:
            return False
        ri.status = RobotStatus.STOPPING
        ok = connector.stop_robot()
        ri.status = RobotStatus.STOPPED
        ri.last_stop = utcnow()
        record_event(session, EventType.ROBOT_STOPPED, "Robot stopped", account_id=ri.account_id)
        return ok

    def restart(self, session: Session, connector: PlatformConnector, ri: RobotInstance) -> bool:
        self.stop(session, connector, ri)
        ok = self.start(session, connector, ri)
        if ok:
            record_event(session, EventType.ROBOT_RESTARTED, "Robot restarted",
                         account_id=ri.account_id)
        return ok

    def heartbeat(self, session: Session, connector: PlatformConnector, ri: RobotInstance) -> bool:
        alive = connector.robot_heartbeat()
        if alive:
            ri.last_heartbeat = utcnow()
            if ri.status != RobotStatus.ACTIVE:
                ri.status = RobotStatus.ACTIVE
        elif ri.status == RobotStatus.ACTIVE:
            ri.status = RobotStatus.ERROR
            raise_alert(session, AlertType.ROBOT_HEARTBEAT_LOST,
                        "Robot heartbeat lost", account_id=ri.account_id)
            record_event(session, EventType.ROBOT_HEARTBEAT_LOST, "Heartbeat lost",
                         account_id=ri.account_id)
        return alive


robot_manager = RobotManager()
