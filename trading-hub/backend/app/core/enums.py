"""Central enumerations shared across the whole engine.

Keeping these in one place avoids magic strings leaking into the database,
the API and the frontend. Every value is a plain string so it serialises
cleanly to JSON and stores readably in SQLite.
"""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String enum whose ``value`` is what gets stored / serialised."""

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class HealthStatus(StrEnum):
    """Aggregate per-account health (see §67)."""

    OPERATIONAL = "operational"
    ATTENTION = "attention"
    ERROR = "error"
    DISCONNECTED = "disconnected"
    PENDING = "pending"  # being provisioned by the add-account workflow


class RobotStatus(StrEnum):
    """Robot lifecycle (see §66)."""

    ACTIVE = "active"
    STOPPED = "stopped"
    STARTING = "starting"
    STOPPING = "stopping"
    ERROR = "error"
    UNKNOWN = "unknown"


class TerminalStatus(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    STARTING = "starting"
    CRASHED = "crashed"
    UNKNOWN = "unknown"


class ConnectionStatus(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"


class RiskMode(StrEnum):
    """§31-34. FIXED_MONEY is the default; DYNAMIC_PERCENT is opt-in."""

    FIXED_MONEY = "fixed_money"
    DYNAMIC_PERCENT = "dynamic_percent"


class RiskReference(StrEnum):
    """Which capital figure the initial risk is computed from (§33)."""

    INITIAL_BALANCE = "initial_balance"
    CURRENT_BALANCE = "current_balance"
    EQUITY = "equity"


class DrawdownType(StrEnum):
    """§49 - never assume a single model across prop firms."""

    STATIC = "static"
    TRAILING = "trailing"
    EQUITY_BASED = "equity_based"
    BALANCE_BASED = "balance_based"
    DAILY_RESET = "daily_reset"


class MappingStatus(StrEnum):
    """Outcome of resolving a universal market to a real symbol (§26-27)."""

    AUTO = "auto"  # confidence >= auto threshold
    NEEDS_CONFIRMATION = "needs_confirmation"  # between thresholds
    UNRESOLVED = "unresolved"  # below lower threshold / not found
    MANUAL = "manual"  # user confirmed a specific symbol


class AssetClass(StrEnum):
    FOREX = "forex"
    METAL = "metal"
    INDEX = "index"
    COMMODITY = "commodity"
    CRYPTO = "crypto"
    STOCK = "stock"
    FUTURE = "future"
    UNKNOWN = "unknown"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(StrEnum):
    """§50 - the catalogue of things worth surfacing."""

    ROBOT_STOPPED = "robot_stopped"
    ROBOT_HEARTBEAT_LOST = "robot_heartbeat_lost"
    TERMINAL_CLOSED = "terminal_closed"
    ACCOUNT_DISCONNECTED = "account_disconnected"
    MARKET_UNRESOLVED = "market_unresolved"
    MARKET_MAPPING_CHANGED = "market_mapping_changed"
    RISK_CONFIGURATION_FAILED = "risk_configuration_failed"
    DRAWDOWN_APPROACHING_LIMIT = "drawdown_approaching_limit"
    DAILY_LOSS_APPROACHING_LIMIT = "daily_loss_approaching_limit"
    PLATFORM_UNAVAILABLE = "platform_unavailable"
    ROBOT_VERSION_MISMATCH = "robot_version_mismatch"
    TEMPLATE_MISMATCH = "template_mismatch"
    RECOVERY_FAILED = "recovery_failed"
    RECOVERY_SUCCEEDED = "recovery_succeeded"


class EventType(StrEnum):
    """Names broadcast on the EventBus and persisted to the event log (§55)."""

    ACCOUNT_CREATED = "account.created"
    ACCOUNT_CONNECTED = "account.connected"
    ACCOUNT_DISCONNECTED = "account.disconnected"
    ACCOUNT_UPDATED = "account.updated"
    ACCOUNT_REMOVED = "account.removed"
    ACCOUNT_STATUS_CHANGED = "account.status_changed"
    WORKFLOW_STEP = "workflow.step"
    TERMINAL_STARTED = "terminal.started"
    TERMINAL_STOPPED = "terminal.stopped"
    TERMINAL_CRASHED = "terminal.crashed"
    ROBOT_STARTED = "robot.started"
    ROBOT_STOPPED = "robot.stopped"
    ROBOT_RESTARTED = "robot.restarted"
    ROBOT_HEARTBEAT = "robot.heartbeat"
    ROBOT_HEARTBEAT_LOST = "robot.heartbeat_lost"
    ROBOT_CONFIGURED = "robot.configured"
    MARKET_MAPPED = "market.mapped"
    MARKET_UNRESOLVED = "market.unresolved"
    RISK_CHANGED = "risk.changed"
    RECOVERY_STARTED = "recovery.started"
    RECOVERY_SUCCEEDED = "recovery.succeeded"
    RECOVERY_FAILED = "recovery.failed"
    ALERT_RAISED = "alert.raised"
    SNAPSHOT = "account.snapshot"


class RecoveryState(StrEnum):
    """States of the auto-healing state machine (§51)."""

    IDLE = "idle"
    DIAGNOSING = "diagnosing"
    RESTARTING_TERMINAL = "restarting_terminal"
    RECONNECTING_ACCOUNT = "reconnecting_account"
    RESTARTING_ROBOT = "restarting_robot"
    WAITING_HEARTBEAT = "waiting_heartbeat"
    RECOVERED = "recovered"
    FAILED = "failed"
