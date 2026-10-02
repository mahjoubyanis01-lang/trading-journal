"""Heartbeat + recovery state machine tests (§51, §66, Acceptance Tests 5 & 6)."""
from datetime import datetime, timedelta, timezone

from app.connectors.mock.mock import MockConnector
from app.core.enums import RecoveryState, RobotStatus
from app.recovery.engine import RecoveryEngine
from app.robots.heartbeat import derive_status, is_alive


def test_heartbeat_alive_within_timeout():
    now = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    assert is_alive(now - timedelta(seconds=30), now, 60)


def test_heartbeat_lost_after_timeout():
    now = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    assert not is_alive(now - timedelta(seconds=120), now, 60)
    assert not is_alive(None, now, 60)


def test_active_robot_without_heartbeat_becomes_error():
    now = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    s = derive_status(RobotStatus.ACTIVE, now - timedelta(seconds=120), now, 60)
    assert s == RobotStatus.ERROR


def _running_connector() -> MockConnector:
    c = MockConnector(seed_balance=10_000)
    c.connect("1001", "pw", "Mock")
    c.create_terminal_instance("MT5-001")
    c.start_robot()
    return c


def test_recover_from_robot_crash():
    # §71 / Test 5 : robot dies, infra healthy => restart succeeds
    c = _running_connector()
    assert c.robot_heartbeat()
    c.sim_crash_robot()
    assert not c.robot_heartbeat()
    report = RecoveryEngine(max_attempts=3).run(c)
    assert report.outcome == RecoveryState.RECOVERED
    assert c.robot_heartbeat()
    assert RecoveryState.RESTARTING_ROBOT in report.transitions


def test_recover_from_terminal_crash():
    # §71 / Test 6 : terminal closes => restart terminal, reconnect, restart robot
    c = _running_connector()
    c.sim_crash_terminal()
    assert not c.terminal_alive()
    report = RecoveryEngine(max_attempts=3).run(c)
    assert report.outcome == RecoveryState.RECOVERED
    assert RecoveryState.RESTARTING_TERMINAL in report.transitions
    assert c.robot_heartbeat()


def test_recovery_fails_when_fault_persists():
    # Persistent heartbeat fault => recovery gives up and asks for a human (§51)
    c = _running_connector()
    c.sim_lose_heartbeat()
    report = RecoveryEngine(max_attempts=3).run(c)
    assert report.outcome == RecoveryState.FAILED
    assert report.attempts == 3
    assert report.transitions[-1] == RecoveryState.FAILED


def test_recovery_never_touches_positions():
    # §52 : recovery must not expose any close/flatten action
    engine = RecoveryEngine()
    for attr in ("close_positions", "flatten", "liquidate"):
        assert not hasattr(engine, attr)
