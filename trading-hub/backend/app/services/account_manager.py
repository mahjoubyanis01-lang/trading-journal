"""Account manager - the add-account orchestration workflow (§11-12, §76).

Runs the DETECT -> CONFIGURE -> EXECUTE -> VERIFY pipeline and emits a
WORKFLOW_STEP event per step so the UI can show live progress (§12). The user
only intervenes when something genuinely cannot be auto-resolved (§64, §77):
an unresolved market leaves the account in ATTENTION with an alert, but the
rest of provisioning still completes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from ..connectors import registry
from ..connectors.base import RobotConfig
from ..core.config import get_settings
from ..core.enums import (
    AlertType,
    ConnectionStatus,
    EventType,
    HealthStatus,
    RiskMode,
    RiskReference,
    TerminalStatus,
)
from ..core.events import Event, bus
from ..database.base import utcnow
from ..database.models import (
    Account,
    AccountCredential,
    AccountSnapshot,
    Broker,
    Platform,
    PropFirm,
    Strategy,
)
from ..risk.engine import resolve_effective_risk
from ..robots.manager import robot_manager
from ..security.credentials import credential_manager
from ..terminal.manager import terminal_manager
from . import market_service, strategy_manager
from .health import HealthSignals, compute_health
from .journal import raise_alert, record_event
from .sessions import sessions


@dataclass(slots=True)
class Step:
    name: str
    ok: bool
    detail: str = ""


def _emit_step(account_id: int, step: Step) -> None:
    bus.publish_soon(Event(EventType.WORKFLOW_STEP, {"account_id": account_id, **asdict(step)}))


def _auto_name(prop_firm_name: str, balance: float) -> str:
    if balance >= 1000:
        size = f"{int(round(balance / 1000))}K"
    else:
        size = f"{int(balance)}"
    return f"{prop_firm_name} {size}"


@dataclass(slots=True)
class AddAccountInput:
    prop_firm_id: int
    platform_key: str
    login: str
    password: str
    server: str | None = None  # broker/server (required by MT5)
    extra: dict | None = None  # platform-specific secrets (api_key, secret, ...)
    name: str | None = None
    strategy_id: int | None = None
    seed_balance: float = 10_000.0  # mock only


def add_account(session: Session, data: AddAccountInput) -> tuple[Account, list[Step]]:
    s = get_settings()
    steps: list[Step] = []

    def step(name: str, ok: bool, detail: str = "") -> None:
        st = Step(name, ok, detail)
        steps.append(st)

    prop = session.get(PropFirm, data.prop_firm_id)
    platform = session.query(Platform).filter(Platform.key == data.platform_key).one_or_none()
    if prop is None or platform is None:
        raise ValueError("Unknown prop firm or platform")

    # 1. validate credentials
    if not data.login or not data.password:
        raise ValueError("Login and password are required")
    step("Validate credentials", True)

    # Create the account row (pending) so children can reference it.
    account = Account(
        name=data.name or f"{prop.name} (pending)", login=data.login,
        prop_firm_id=prop.id, platform_id=platform.id, strategy_id=data.strategy_id,
        health=HealthStatus.PENDING, connection=ConnectionStatus.CONNECTING,
        initial_balance=0.0, balance=0.0, equity=0.0,
    )
    session.add(account)
    session.flush()
    _emit_step(account.id, steps[-1])

    # 2. store credentials in the OS secret store (never in DB) (§7)
    secret_ref = credential_manager.store(account.id, data.password)
    session.add(AccountCredential(account_id=account.id, secret_ref=secret_ref))
    extra_in = data.extra or {}
    for field, value in extra_in.items():
        if value:
            credential_manager.store_field(account.id, field, value)
    step("Secure credentials", True, f"stored via {credential_manager.backend()}")
    _emit_step(account.id, steps[-1])

    # Record the broker/server so it shows in the UI and drives the connection.
    if data.server:
        broker = (
            session.query(Broker)
            .filter(Broker.server == data.server, Broker.prop_firm_id == prop.id)
            .one_or_none()
        )
        if broker is None:
            broker = Broker(name=f"{prop.name} ({data.server})", server=data.server,
                            prop_firm_id=prop.id)
            session.add(broker)
            session.flush()
        account.broker_id = broker.id

    # 3. create connector + verify it can actually operate on this machine (§88)
    kwargs = {"seed_balance": data.seed_balance} if data.platform_key == "mock" else {}
    connector = registry.create(data.platform_key, **kwargs)
    caps = connector.capabilities()
    if not caps.can_connect:
        account.health = HealthStatus.ERROR
        account.connection = ConnectionStatus.ERROR
        step("Connect", False, f"{platform.name} runtime unavailable on this machine")
        _emit_step(account.id, steps[-1])
        raise_alert(session, AlertType.PLATFORM_UNAVAILABLE,
                    f"{platform.name} unavailable - account provisioned but offline",
                    account_id=account.id)
        session.flush()
        return account, steps

    # 4. create the dedicated terminal instance FIRST (MT5 connects through it,
    #    and each account gets its own isolated portable terminal §14-15).
    ti = terminal_manager.allocate(session, connector, account.id, data.platform_key)
    step("Terminal instance", True, ti.instance_id)
    _emit_step(account.id, steps[-1])

    # 5. connect (MT5 initialises against the instance created above)
    extra_secrets = {
        f.name: credential_manager.retrieve_field(account.id, f.name) or extra_in.get(f.name, "")
        for f in connector.extra_credential_fields()
    }
    result = connector.connect(
        data.login, credential_manager.retrieve(secret_ref) or "", data.server,
        extra_secrets,
    )
    if not result.ok:
        account.health = HealthStatus.DISCONNECTED
        account.connection = ConnectionStatus.ERROR
        step("Connect", False, result.message)
        _emit_step(account.id, steps[-1])
        raise_alert(session, AlertType.ACCOUNT_DISCONNECTED, result.message, account_id=account.id)
        session.flush()
        return account, steps
    sessions.set(account.id, connector)
    account.connection = ConnectionStatus.CONNECTED
    step("Connect", True, f"server {result.account.server}")
    _emit_step(account.id, steps[-1])

    # 6. read account + auto-name
    info = connector.get_account_info()
    account.initial_balance = info.balance
    account.balance = info.balance
    account.equity = info.equity
    account.currency = info.currency
    if not data.name:
        account.name = _auto_name(prop.name, info.balance)
    step("Read account", True, f"balance {info.balance} {info.currency}")
    _emit_step(account.id, steps[-1])

    # 8-9. strategy + robot instance
    strategy = (
        session.get(Strategy, data.strategy_id) if data.strategy_id
        else strategy_manager.get_default_strategy(session)
    )
    if strategy is None:
        raise ValueError("No strategy available - seed a default strategy first")
    account.strategy_id = strategy.id
    version = strategy_manager.current_robot_version(session, strategy.id)
    ri = robot_manager.ensure_instance(session, account.id, strategy.id, version, ti.instance_id)
    step("Strategy & robot", True, f"{strategy.name} {version or ''}".strip())
    _emit_step(account.id, steps[-1])

    # 10. discover + map markets
    mk = market_service.discover_and_map(
        session, connector, account.id, account.broker_id, data.platform_key,
        strategy.market_list(),
    )
    resolved_n = len(mk["resolved"])
    total_n = resolved_n + len(mk["unresolved"])
    step("Markets", not mk["unresolved"],
         f"{resolved_n}/{total_n} mapped" + (f", unresolved: {', '.join(mk['unresolved'])}" if mk["unresolved"] else ""))
    _emit_step(account.id, steps[-1])

    # 11. risk (fixed money from 0.5% of initial balance by default) (§32)
    risk = resolve_effective_risk(
        account_mode=account.risk_mode, account_amount=account.risk_amount,
        account_percent=account.risk_percent, account_reference=account.risk_reference,
        strategy_mode=RiskMode(strategy.default_risk_mode),
        strategy_percent=strategy.default_risk_percent,
        strategy_reference=RiskReference(strategy.default_risk_reference),
        initial_balance=account.initial_balance, current_balance=account.balance, equity=account.equity,
    )
    step("Risk", True, f"{risk.mode.value} {risk.amount} {account.currency}")
    _emit_step(account.id, steps[-1])

    # 12. configure robot with real symbols
    real_symbols = [r["real"] for r in mk["resolved"]]
    cfg = RobotConfig(risk_mode=risk.mode.value, risk_amount=risk.amount, markets=real_symbols)
    configured = robot_manager.install_and_configure(
        connector, strategy_manager.robot_file(session, strategy.id, version), cfg
    )
    step("Configure robot", configured, "")
    _emit_step(account.id, steps[-1])

    # 13. template
    tpl = account.template_name or strategy.template_name
    applied = terminal_manager.apply_template(connector, tpl)
    terminal_manager.mark_status(session, ti.instance_id, TerminalStatus.RUNNING)
    step("Apply template", applied, tpl)
    _emit_step(account.id, steps[-1])

    # 14-15. start robot + heartbeat (respect auto-start)
    auto_start = account.auto_start if account.auto_start is not None else strategy.auto_start
    if auto_start and configured:
        robot_manager.start(session, connector, ri)
        hb = robot_manager.heartbeat(session, connector, ri)
        step("Start robot", hb, "heartbeat OK" if hb else "no heartbeat")
        _emit_step(account.id, steps[-1])

    # 16. final health
    account.health = compute_health(HealthSignals(
        connection=account.connection, terminal=ti.status, robot=ri.status,
        heartbeat_ok=connector.robot_heartbeat(),
        has_unresolved_market=bool(mk["unresolved"]),
    ))
    record_event(session, EventType.ACCOUNT_CREATED,
                 f"Account {account.name} provisioned ({account.health.value})", account_id=account.id)

    # 17. snapshot
    session.add(AccountSnapshot(account_id=account.id, ts=utcnow(),
                                balance=account.balance, equity=account.equity))
    step("Verify", account.health != HealthStatus.ERROR, account.health.value)
    _emit_step(account.id, steps[-1])

    session.flush()
    return account, steps


def remove_account(session: Session, account_id: int) -> None:
    account = session.get(Account, account_id)
    if account is None:
        return
    connector = sessions.get(account_id)
    if connector is not None:
        try:
            if connector.capabilities().can_stop_robot:
                connector.stop_robot()
        finally:
            connector.disconnect()
        sessions.drop(account_id)
    if account.credential:
        credential_manager.delete(account.credential.secret_ref)
    # Also purge any extra secret fields (api_key/secret/...) for this platform.
    try:
        from ..connectors import registry as _reg
        fields = [f.name for f in _reg.create(account.platform.key).extra_credential_fields()]
        credential_manager.delete_account(account.id, fields)
    except Exception:  # noqa: BLE001
        pass
    record_event(session, EventType.ACCOUNT_REMOVED, f"Account {account.name} removed",
                 account_id=None)
    session.delete(account)
    session.flush()
