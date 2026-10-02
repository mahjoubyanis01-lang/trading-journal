"""Terminal manager (§13-15).

Allocates and tracks one terminal instance per account so instances never mix
accounts or overwrite each other's data (§14-15). Each instance gets a stable
id (e.g. ``MT5-001``), its own terminal_path/data_path and process id.

On Windows the real work (copying a portable terminal folder, launching with
``/portable``, polling the process) is done here via the connector + OS calls.
In mock mode the connector simulates it. Detection of installed platforms is a
documented stub until the Windows agent fills it in (§88 - no fabricated paths).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..connectors.base import PlatformConnector
from ..core.enums import EventType, TerminalStatus
from ..database.base import utcnow
from ..database.models import TerminalInstance
from ..services.journal import record_event


class TerminalManager:
    def _next_instance_id(self, session: Session, platform_key: str) -> str:
        prefix = platform_key.upper()
        count = (
            session.query(TerminalInstance)
            .filter(TerminalInstance.platform_key == platform_key)
            .count()
        )
        return f"{prefix}-{count + 1:03d}"

    def allocate(
        self, session: Session, connector: PlatformConnector, account_id: int, platform_key: str
    ) -> TerminalInstance:
        """Create (or reuse) a dedicated terminal instance for an account."""
        existing = (
            session.query(TerminalInstance)
            .filter(TerminalInstance.account_id == account_id)
            .one_or_none()
        )
        if existing:
            return existing

        instance_id = self._next_instance_id(session, platform_key)
        info = {}
        if connector.capabilities().can_create_terminal_instance:
            info = connector.create_terminal_instance(instance_id)

        ti = TerminalInstance(
            instance_id=instance_id, account_id=account_id, platform_key=platform_key,
            terminal_path=info.get("terminal_path"), data_path=info.get("data_path"),
            process_id=info.get("process_id"), status=TerminalStatus.RUNNING,
            last_heartbeat=utcnow(),
        )
        session.add(ti)
        session.flush()
        record_event(session, EventType.TERMINAL_STARTED,
                     f"Terminal {instance_id} ready", account_id=account_id,
                     instance_id=instance_id)
        return ti

    def apply_template(self, connector: PlatformConnector, template_name: str) -> bool:
        if not connector.capabilities().can_apply_template:
            return False
        return connector.apply_template(template_name)

    def mark_status(self, session: Session, instance_id: str, status: TerminalStatus) -> None:
        ti = (
            session.query(TerminalInstance)
            .filter(TerminalInstance.instance_id == instance_id)
            .one_or_none()
        )
        if ti:
            ti.status = status
            if status == TerminalStatus.RUNNING:
                ti.last_heartbeat = utcnow()

    @staticmethod
    def detect_installations(platform_key: str) -> list[dict]:
        """Returns installed terminal paths. Real implementation lives in the
        Windows agent (registry + common install dirs); here we return [] rather
        than inventing paths (§88)."""
        return []


terminal_manager = TerminalManager()
