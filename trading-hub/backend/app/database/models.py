"""ORM schema (§6).

Modelling choices that matter:
- PropFirm / Broker / Platform / Account are distinct (§10): a prop firm is
  not a platform, so we never hard-code one firm or one platform (§94).
- account_credentials stores only a *handle* into the OS secret store, never
  the secret itself (§7).
- Risk is stored as mode + amount + reference, never as a bare percentage
  (§90), so the UI can always show the full picture.
- Market mapping is keyed by (broker, platform, universal market) and carries
  a confidence score (§26) so a validated mapping can be reused - but the
  per-account table still forces a per-account existence check (§30).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.enums import (
    AlertSeverity,
    AlertType,
    ConnectionStatus,
    DrawdownType,
    HealthStatus,
    MappingStatus,
    RiskMode,
    RiskReference,
    RobotStatus,
    TerminalStatus,
)
from .base import Base


class PropFirm(Base):
    __tablename__ = "prop_firms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    website: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    accounts: Mapped[list["Account"]] = relationship(back_populates="prop_firm")
    drawdown_rules: Mapped[list["DrawdownRule"]] = relationship(
        back_populates="prop_firm", cascade="all, delete-orphan"
    )


class Broker(Base):
    __tablename__ = "brokers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    server: Mapped[str | None] = mapped_column(String(160))
    prop_firm_id: Mapped[int | None] = mapped_column(ForeignKey("prop_firms.id"))


class Platform(Base):
    __tablename__ = "platforms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)  # connector key
    name: Mapped[str] = mapped_column(String(80))


class Strategy(Base):
    __tablename__ = "strategies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Default parameters inherited by every account unless overridden (§59, §91).
    default_risk_mode: Mapped[RiskMode] = mapped_column(String(20), default=RiskMode.FIXED_MONEY)
    default_risk_percent: Mapped[float] = mapped_column(Float, default=0.5)
    default_risk_reference: Mapped[RiskReference] = mapped_column(
        String(20), default=RiskReference.INITIAL_BALANCE
    )
    auto_start: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_recovery: Mapped[bool] = mapped_column(Boolean, default=True)
    # Universal markets (comma-separated universal symbols) and template.
    markets: Mapped[str] = mapped_column(Text, default="")
    template_name: Mapped[str] = mapped_column(String(80), default="Default MT5")
    schedule: Mapped[str | None] = mapped_column(String(120))

    robot_versions: Mapped[list["RobotVersion"]] = relationship(
        back_populates="strategy", cascade="all, delete-orphan"
    )
    accounts: Mapped[list["Account"]] = relationship(back_populates="strategy")

    def market_list(self) -> list[str]:
        return [m.strip() for m in self.markets.split(",") if m.strip()]


class RobotVersion(Base):
    __tablename__ = "robot_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id"))
    version: Mapped[str] = mapped_column(String(40))  # e.g. "1.4.2"
    robot_file: Mapped[str | None] = mapped_column(String(255))  # e.g. StrategyA.ex5
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    strategy: Mapped["Strategy"] = relationship(back_populates="robot_versions")


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    login: Mapped[str] = mapped_column(String(80))  # trading login (not secret)
    prop_firm_id: Mapped[int] = mapped_column(ForeignKey("prop_firms.id"))
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"))
    broker_id: Mapped[int | None] = mapped_column(ForeignKey("brokers.id"))
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("strategies.id"))

    health: Mapped[HealthStatus] = mapped_column(String(20), default=HealthStatus.PENDING)
    connection: Mapped[ConnectionStatus] = mapped_column(
        String(20), default=ConnectionStatus.DISCONNECTED
    )

    initial_balance: Mapped[float] = mapped_column(Float, default=0.0)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    equity: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="USD")

    # Per-account risk override (§59). NULL => inherit from strategy.
    risk_mode: Mapped[RiskMode | None] = mapped_column(String(20))
    risk_amount: Mapped[float | None] = mapped_column(Float)
    risk_percent: Mapped[float | None] = mapped_column(Float)
    risk_reference: Mapped[RiskReference | None] = mapped_column(String(20))

    auto_start: Mapped[bool | None] = mapped_column(Boolean)
    auto_recovery: Mapped[bool | None] = mapped_column(Boolean)
    template_name: Mapped[str | None] = mapped_column(String(80))

    prop_firm: Mapped["PropFirm"] = relationship(back_populates="accounts")
    platform: Mapped["Platform"] = relationship()
    broker: Mapped["Broker | None"] = relationship()
    strategy: Mapped["Strategy | None"] = relationship(back_populates="accounts")
    credential: Mapped["AccountCredential | None"] = relationship(
        back_populates="account", cascade="all, delete-orphan", uselist=False
    )
    robot: Mapped["RobotInstance | None"] = relationship(
        back_populates="account", cascade="all, delete-orphan", uselist=False
    )
    terminal: Mapped["TerminalInstance | None"] = relationship(
        back_populates="account", cascade="all, delete-orphan", uselist=False
    )


class AccountCredential(Base):
    """Never stores the password. ``secret_ref`` is a handle into the OS
    secret store (Windows Credential Manager / keyring); see §7."""

    __tablename__ = "account_credentials"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), unique=True)
    secret_ref: Mapped[str] = mapped_column(String(160))
    account: Mapped["Account"] = relationship(back_populates="credential")


class TerminalInstance(Base):
    __tablename__ = "terminal_instances"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(40), unique=True)  # e.g. MT5-017
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    platform_key: Mapped[str] = mapped_column(String(40))
    terminal_path: Mapped[str | None] = mapped_column(String(400))
    data_path: Mapped[str | None] = mapped_column(String(400))
    process_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[TerminalStatus] = mapped_column(String(20), default=TerminalStatus.STOPPED)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime)
    account: Mapped["Account | None"] = relationship(back_populates="terminal")


class RobotInstance(Base):
    __tablename__ = "robot_instances"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), unique=True)
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("strategies.id"))
    robot_version: Mapped[str | None] = mapped_column(String(40))
    terminal_instance_id: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[RobotStatus] = mapped_column(String(20), default=RobotStatus.STOPPED)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime)
    last_start: Mapped[datetime | None] = mapped_column(DateTime)
    last_stop: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    account: Mapped["Account"] = relationship(back_populates="robot")


class UniversalMarket(Base):
    """market_definitions (§23). Platform-agnostic market identities."""

    __tablename__ = "market_definitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(40), unique=True)  # e.g. NASDAQ100
    description: Mapped[str | None] = mapped_column(String(160))
    asset_class: Mapped[str] = mapped_column(String(20), default="unknown")
    aliases: Mapped[str] = mapped_column(Text, default="")  # comma-separated


class MarketMapping(Base):
    """Reusable mapping of a universal market to a real symbol for a given
    broker+platform (§26, §30). Still re-verified per account before use."""

    __tablename__ = "market_mappings"
    __table_args__ = (
        UniqueConstraint("universal_symbol", "broker_id", "platform_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    universal_symbol: Mapped[str] = mapped_column(String(40))
    broker_id: Mapped[int | None] = mapped_column(ForeignKey("brokers.id"))
    platform_key: Mapped[str] = mapped_column(String(40))
    real_symbol: Mapped[str] = mapped_column(String(60))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[MappingStatus] = mapped_column(String(24), default=MappingStatus.AUTO)


class AccountMarketMapping(Base):
    """Per-account resolved symbol (§30 - verify existence per account)."""

    __tablename__ = "account_market_mappings"
    __table_args__ = (UniqueConstraint("account_id", "universal_symbol"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    universal_symbol: Mapped[str] = mapped_column(String(40))
    real_symbol: Mapped[str | None] = mapped_column(String(60))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[MappingStatus] = mapped_column(String(24), default=MappingStatus.UNRESOLVED)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class DrawdownRule(Base):
    """Per-prop-firm drawdown configuration (§48-49)."""

    __tablename__ = "drawdown_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prop_firm_id: Mapped[int] = mapped_column(ForeignKey("prop_firms.id"))
    dd_type: Mapped[DrawdownType] = mapped_column(String(20), default=DrawdownType.STATIC)
    daily_loss_pct: Mapped[float | None] = mapped_column(Float)
    max_total_loss_pct: Mapped[float | None] = mapped_column(Float)
    prop_firm: Mapped["PropFirm"] = relationship(back_populates="drawdown_rules")


class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    ts: Mapped[datetime] = mapped_column(DateTime)
    balance: Mapped[float] = mapped_column(Float)
    equity: Mapped[float] = mapped_column(Float)


class DailyPerformance(Base):
    __tablename__ = "daily_performance"
    __table_args__ = (UniqueConstraint("account_id", "day"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    day: Mapped[date] = mapped_column(Date)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    balance_close: Mapped[float] = mapped_column(Float, default=0.0)
    equity_close: Mapped[float] = mapped_column(Float, default=0.0)


class MonthlyPerformance(Base):
    __tablename__ = "monthly_performance"
    __table_args__ = (UniqueConstraint("account_id", "year", "month"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    performance_pct: Mapped[float] = mapped_column(Float, default=0.0)


class DrawdownSnapshot(Base):
    __tablename__ = "drawdown_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    ts: Mapped[datetime] = mapped_column(DateTime)
    current_dd_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_dd_pct: Mapped[float] = mapped_column(Float, default=0.0)


class Position(Base):
    """Monitoring only - never used to copy trades (§2, §56)."""

    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    symbol: Mapped[str] = mapped_column(String(60))
    volume: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(8))  # buy / sell
    open_price: Mapped[float] = mapped_column(Float, default=0.0)
    profit: Mapped[float] = mapped_column(Float, default=0.0)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    symbol: Mapped[str] = mapped_column(String(60))
    volume: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(20), default="open")


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    type: Mapped[AlertType] = mapped_column(String(40))
    severity: Mapped[AlertSeverity] = mapped_column(String(12), default=AlertSeverity.WARNING)
    message: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    ts: Mapped[datetime] = mapped_column(DateTime)


class EventLog(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    type: Mapped[str] = mapped_column(String(48))
    message: Mapped[str] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime)


class TerminalLog(Base):
    __tablename__ = "terminal_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    terminal_instance_id: Mapped[str] = mapped_column(String(40))
    level: Mapped[str] = mapped_column(String(12), default="info")
    message: Mapped[str] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime)


class RobotLog(Base):
    __tablename__ = "robot_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    level: Mapped[str] = mapped_column(String(12), default="info")
    message: Mapped[str] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime)


class ConfigurationVersion(Base):
    """Snapshot of an account's important config for audit (§54)."""

    __tablename__ = "configuration_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    payload: Mapped[str] = mapped_column(Text)  # JSON blob
    ts: Mapped[datetime] = mapped_column(DateTime)


class Setting(Base):
    """Key/value global settings editable at runtime (§74)."""

    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True)
    value: Mapped[str] = mapped_column(Text)
