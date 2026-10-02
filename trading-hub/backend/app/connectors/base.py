"""Platform connector abstraction (§8-9).

Every platform (MT5, MT4, cTrader, Tradovate, ...) is reached through a
subclass of :class:`PlatformConnector`. The core engine only ever talks to
this interface, so a new platform is added by writing one connector - without
touching the rest of the app (§8, §94).

Two rules enforced here:
- A connector declares its real :class:`PlatformCapabilities` (§9). The core
  and the UI must respect them and never offer an action a platform can't do.
- A connector never invents financial data (§88). When an instrument field is
  unknown it stays ``None``; the risk engine then refuses to guess a volume.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field

from ..core.enums import AssetClass


@dataclass(slots=True)
class PlatformCapabilities:
    """Mirror of the TS interface in §9. All default to False: a connector
    must explicitly opt in to each capability it genuinely supports."""

    can_connect: bool = False
    can_read_account: bool = False
    can_read_balance: bool = False
    can_read_equity: bool = False
    can_read_positions: bool = False
    can_read_orders: bool = False
    can_discover_markets: bool = False
    can_start_robot: bool = False
    can_stop_robot: bool = False
    can_restart_robot: bool = False
    can_install_robot: bool = False
    can_configure_robot: bool = False
    can_create_terminal_instance: bool = False
    can_apply_template: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class InstrumentInfo:
    """A tradable instrument as reported by the platform (§24).

    Unknown numeric fields stay ``None`` - the risk engine treats ``None`` as
    "cannot size safely" rather than substituting a default (§88)."""

    symbol: str
    description: str | None = None
    asset_class: AssetClass = AssetClass.UNKNOWN
    base_currency: str | None = None
    quote_currency: str | None = None
    contract_size: float | None = None
    tick_size: float | None = None
    tick_value: float | None = None
    volume_min: float | None = None
    volume_max: float | None = None
    volume_step: float | None = None
    digits: int | None = None
    trade_mode: str | None = None
    expiration: str | None = None

    def as_dict(self) -> dict:
        d = asdict(self)
        d["asset_class"] = self.asset_class.value
        return d


@dataclass(slots=True)
class AccountInfo:
    login: str
    balance: float
    equity: float
    currency: str = "USD"
    server: str | None = None
    broker: str | None = None
    leverage: int | None = None


@dataclass(slots=True)
class PositionInfo:
    symbol: str
    volume: float
    direction: str  # "buy" / "sell"
    open_price: float = 0.0
    profit: float = 0.0


@dataclass(slots=True)
class ConnectResult:
    ok: bool
    account: AccountInfo | None = None
    message: str = ""


@dataclass(slots=True)
class RobotConfig:
    """What we hand to a robot instance (§22, §90)."""

    risk_mode: str
    risk_amount: float
    markets: list[str] = field(default_factory=list)  # real symbols
    parameters: dict = field(default_factory=dict)


class ConnectorError(RuntimeError):
    pass


class CapabilityError(ConnectorError):
    """Raised when an action is requested that the connector cannot perform."""


class PlatformConnector(ABC):
    """Base class. A connector instance is bound to one account's session.

    Subclasses MUST set ``key`` and implement :meth:`capabilities`. Everything
    else has a safe default that raises :class:`CapabilityError`, so a partial
    connector can never silently pretend to support an action (§9, §94)."""

    key: str = "base"
    display_name: str = "Base"

    def __init__(self) -> None:
        self._connected = False

    # --- capability declaration -----------------------------------------
    @abstractmethod
    def capabilities(self) -> PlatformCapabilities: ...

    @classmethod
    def requirement(cls) -> str:
        """Human-readable note on what this connector needs to operate.
        Empty string means "ready". Surfaced in the UI so limitations are
        never hidden (§88, §92)."""
        return ""

    def _require(self, flag: str) -> None:
        caps = self.capabilities()
        if not getattr(caps, flag, False):
            raise CapabilityError(f"{self.display_name} does not support {flag}")

    # --- connection ------------------------------------------------------
    def connect(self, login: str, password: str, server: str | None = None) -> ConnectResult:
        self._require("can_connect")
        raise NotImplementedError

    def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # --- account / market reads -----------------------------------------
    def get_account_info(self) -> AccountInfo:
        self._require("can_read_account")
        raise NotImplementedError

    def get_available_markets(self) -> list[InstrumentInfo]:
        self._require("can_discover_markets")
        raise NotImplementedError

    def get_instrument(self, symbol: str) -> InstrumentInfo | None:
        for inst in self.get_available_markets():
            if inst.symbol == symbol:
                return inst
        return None

    def get_positions(self) -> list[PositionInfo]:
        self._require("can_read_positions")
        raise NotImplementedError

    def get_orders(self) -> list[PositionInfo]:
        self._require("can_read_orders")
        return []

    # --- terminal / template --------------------------------------------
    def create_terminal_instance(self, instance_id: str) -> dict:
        self._require("can_create_terminal_instance")
        raise NotImplementedError

    def apply_template(self, template_name: str) -> bool:
        self._require("can_apply_template")
        raise NotImplementedError

    # --- robot lifecycle -------------------------------------------------
    def install_robot(self, robot_file: str | None) -> bool:
        self._require("can_install_robot")
        raise NotImplementedError

    def configure_robot(self, config: RobotConfig) -> bool:
        self._require("can_configure_robot")
        raise NotImplementedError

    def start_robot(self) -> bool:
        self._require("can_start_robot")
        raise NotImplementedError

    def stop_robot(self) -> bool:
        self._require("can_stop_robot")
        raise NotImplementedError

    def restart_robot(self) -> bool:
        self._require("can_restart_robot")
        self.stop_robot()
        return self.start_robot()

    def robot_heartbeat(self) -> bool:
        """Return True if the robot is alive right now."""
        return False

    # --- recovery surface (§51) -----------------------------------------
    # Default implementations let the RecoveryEngine drive any connector.
    # NOTE: recovery restores *infrastructure* only - it must never close or
    # flatten positions (§52).
    def terminal_alive(self) -> bool:
        return True

    def account_alive(self) -> bool:
        return self._connected

    def restart_terminal(self) -> bool:
        return True

    def reconnect_account(self) -> bool:
        return self._connected
