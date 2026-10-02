"""Seed reference data + optional demo accounts (§70, §75).

Reference data (platforms, a starter set of prop firms, universal markets,
the default strategy) is idempotent. Demo accounts are created through the real
AccountManager workflow so the mock mode exercises the exact same code path as
production (§70, Acceptance Test 7)."""
from __future__ import annotations

import random

from sqlalchemy.orm import Session

from ..core.enums import AssetClass, DrawdownType, RiskMode, RiskReference
from ..markets.universal import DEFAULT_UNIVERSAL
from .models import (
    Account,
    DrawdownRule,
    Platform,
    PropFirm,
    RobotVersion,
    Setting,
    Strategy,
    UniversalMarket,
)

PLATFORMS = [
    ("mock", "Mock Platform"),
    ("mt5", "MetaTrader 5"),
    ("mt4", "MetaTrader 4"),
    ("ctrader", "cTrader"),
    ("tradovate", "Tradovate"),
    ("ninjatrader", "NinjaTrader"),
    ("rithmic", "Rithmic"),
    ("dxtrade", "DXtrade"),
    ("matchtrader", "Match-Trader"),
    ("tradelocker", "TradeLocker"),
    ("quantower", "Quantower"),
]

# (name, daily %, max total %, drawdown type)
PROP_FIRMS = [
    ("FundedNext", 5.0, 10.0, DrawdownType.BALANCE_BASED),
    ("FundingPips", 5.0, 10.0, DrawdownType.STATIC),
    ("Blue Guardian", 4.0, 8.0, DrawdownType.TRAILING),
    ("FTMO", 5.0, 10.0, DrawdownType.STATIC),
    ("The5ers", 5.0, 10.0, DrawdownType.TRAILING),
    ("Alpha Capital", 5.0, 10.0, DrawdownType.EQUITY_BASED),
]

DEFAULT_MARKETS = "EURUSD,GBPUSD,USDJPY,XAUUSD,NASDAQ100,US30"


def seed_reference(session: Session) -> None:
    if session.query(Platform).count() == 0:
        for key, name in PLATFORMS:
            session.add(Platform(key=key, name=name))

    if session.query(PropFirm).count() == 0:
        for name, daily, total, dd in PROP_FIRMS:
            pf = PropFirm(name=name, website=None)
            session.add(pf)
            session.flush()
            session.add(DrawdownRule(prop_firm_id=pf.id, dd_type=dd,
                                     daily_loss_pct=daily, max_total_loss_pct=total))

    if session.query(UniversalMarket).count() == 0:
        for u in DEFAULT_UNIVERSAL:
            session.add(UniversalMarket(
                symbol=u.symbol, description=u.description,
                asset_class=u.asset_class.value, aliases=",".join(u.aliases),
            ))

    if session.query(Strategy).count() == 0:
        strat = Strategy(
            name="Strategy A", enabled=True,
            default_risk_mode=RiskMode.FIXED_MONEY, default_risk_percent=0.5,
            default_risk_reference=RiskReference.INITIAL_BALANCE,
            auto_start=True, auto_recovery=True, markets=DEFAULT_MARKETS,
            template_name="Default MT5",
        )
        session.add(strat)
        session.flush()
        session.add(RobotVersion(strategy_id=strat.id, version="1.4.2",
                                 robot_file="StrategyA.ex5", is_current=True))

    defaults = {
        "default_risk_percent": "0.5", "default_risk_mode": "fixed_money",
        "auto_start": "true", "auto_recovery": "true",
        "market_discovery": "true", "auto_mapping": "true",
        "confidence_auto": "90", "confidence_confirm": "70",
        "mt5_template": "Default MT5",
    }
    existing = {s.key for s in session.query(Setting).all()}
    for k, v in defaults.items():
        if k not in existing:
            session.add(Setting(key=k, value=v))
    session.commit()


# Account sizes commonly sold by prop firms, in USD.
_SIZES = [5_000, 10_000, 25_000, 50_000, 100_000, 200_000]


def seed_demo_accounts(session: Session, n: int = 50) -> int:
    """Provision N mock accounts through the real workflow (§70, Test 7)."""
    from ..services.account_manager import AddAccountInput, add_account

    from datetime import date, timedelta

    from .models import DailyPerformance

    firms = session.query(PropFirm).all()
    mock_platform = session.query(Platform).filter(Platform.key == "mock").one()
    created = 0
    rnd = random.Random(42)
    today = date.today()
    offset = session.query(Account).count()
    for i in range(offset, offset + n):
        firm = firms[i % len(firms)]
        size = rnd.choice(_SIZES)
        account, _ = add_account(session, AddAccountInput(
            prop_firm_id=firm.id, platform_key=mock_platform.key,
            login=str(500000 + i), password="demo-password",
            name=None, seed_balance=float(size),
        ))
        # Simulate month-to-date P&L so the dashboard has real signal, and
        # write daily rows for the last few days (one slightly negative).
        month_pnl = round(rnd.uniform(-0.03, 0.09) * size, 2)
        account.balance = round(account.initial_balance + month_pnl, 2)
        account.equity = round(account.balance - rnd.uniform(0, 0.004) * size, 2)
        for d in range(5):
            day = today - timedelta(days=4 - d)
            pnl = round(month_pnl / 5 * rnd.uniform(0.3, 1.7) * (1 if rnd.random() > 0.25 else -1), 2)
            session.add(DailyPerformance(
                account_id=account.id, day=day, pnl=pnl,
                balance_close=account.balance, equity_close=account.equity,
            ))
        created += 1
    session.commit()
    return created
