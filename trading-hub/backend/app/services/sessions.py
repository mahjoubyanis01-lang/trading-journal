"""Live session registry.

Maps account_id -> live PlatformConnector so the terminal/robot/recovery
managers all share one connector instance per account (keeping simulated or
real platform state consistent). Purely in-memory; rebuilt on startup by the
agent reconnecting accounts (§65)."""
from __future__ import annotations

from ..connectors.base import PlatformConnector


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[int, PlatformConnector] = {}

    def get(self, account_id: int) -> PlatformConnector | None:
        return self._sessions.get(account_id)

    def set(self, account_id: int, connector: PlatformConnector) -> None:
        self._sessions[account_id] = connector

    def drop(self, account_id: int) -> None:
        self._sessions.pop(account_id, None)

    def all(self) -> dict[int, PlatformConnector]:
        return dict(self._sessions)


sessions = SessionRegistry()
