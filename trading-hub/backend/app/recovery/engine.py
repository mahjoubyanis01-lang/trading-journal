"""Auto-healing recovery state machine (§51-52).

Given a failing account, try to restore the *infrastructure* - terminal,
connection, robot - in the right order, retrying up to a configurable number of
attempts. It NEVER closes or flattens positions (§52): recovery restores plumbing,
it does not make financial decisions.

The engine is driven through a small structural interface (any object exposing
``terminal_alive``, ``account_alive``, ``robot_heartbeat``, ``restart_terminal``,
``reconnect_account``, ``restart_robot``). Both the Mock and real connectors
satisfy it, which keeps the state machine fully unit-testable (§71, Tests 5 & 6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..core.enums import RecoveryState


class RecoveryTarget(Protocol):
    def terminal_alive(self) -> bool: ...
    def account_alive(self) -> bool: ...
    def robot_heartbeat(self) -> bool: ...
    def restart_terminal(self) -> bool: ...
    def reconnect_account(self) -> bool: ...
    def restart_robot(self) -> bool: ...


@dataclass(slots=True)
class RecoveryReport:
    outcome: RecoveryState  # RECOVERED | FAILED
    attempts: int
    transitions: list[RecoveryState] = field(default_factory=list)
    detail: str = ""


class RecoveryEngine:
    def __init__(self, max_attempts: int = 3) -> None:
        self.max_attempts = max_attempts

    def run(self, target: RecoveryTarget) -> RecoveryReport:
        transitions: list[RecoveryState] = []

        for attempt in range(1, self.max_attempts + 1):
            transitions.append(RecoveryState.DIAGNOSING)

            if not target.terminal_alive():
                transitions.append(RecoveryState.RESTARTING_TERMINAL)
                target.restart_terminal()
                transitions.append(RecoveryState.RECONNECTING_ACCOUNT)
                target.reconnect_account()
                transitions.append(RecoveryState.RESTARTING_ROBOT)
                target.restart_robot()
            elif not target.account_alive():
                transitions.append(RecoveryState.RECONNECTING_ACCOUNT)
                target.reconnect_account()
                transitions.append(RecoveryState.RESTARTING_ROBOT)
                target.restart_robot()
            else:
                # terminal + account OK => robot heartbeat was lost
                transitions.append(RecoveryState.RESTARTING_ROBOT)
                target.restart_robot()

            transitions.append(RecoveryState.WAITING_HEARTBEAT)
            if target.robot_heartbeat():
                transitions.append(RecoveryState.RECOVERED)
                return RecoveryReport(
                    RecoveryState.RECOVERED, attempt, transitions, "heartbeat restored"
                )

        transitions.append(RecoveryState.FAILED)
        return RecoveryReport(
            RecoveryState.FAILED, self.max_attempts, transitions,
            "heartbeat not restored after retries - manual intervention required",
        )
