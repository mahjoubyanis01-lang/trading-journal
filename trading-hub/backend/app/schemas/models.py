"""Request/response schemas (API boundary).

Note: passwords only ever appear on the *inbound* AddAccount body; they are
immediately handed to the secret store and never echoed back (§7)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..core.enums import RiskMode


class AddAccountBody(BaseModel):
    prop_firm_id: int
    platform_key: str
    login: str
    password: str = Field(repr=False)  # never logged
    name: str | None = None
    strategy_id: int | None = None
    seed_balance: float = 10_000.0  # mock only


class RiskUpdateBody(BaseModel):
    mode: RiskMode = RiskMode.FIXED_MONEY
    amount: float
    confirm: bool = False


class MassRiskBody(BaseModel):
    account_ids: list[int] = Field(default_factory=list)
    strategy_id: int | None = None
    amount: float
    mode: RiskMode = RiskMode.FIXED_MONEY
    confirm: bool = False


class MarketSearchBody(BaseModel):
    universal_symbol: str


class MarketConfirmBody(BaseModel):
    universal_symbol: str
    real_symbol: str


class MassActionBody(BaseModel):
    account_ids: list[int]
    action: str  # start | stop | restart


class SeedDemoBody(BaseModel):
    count: int = 50


class SimFaultBody(BaseModel):
    fault: str  # robot | terminal | heartbeat | connection | restore
