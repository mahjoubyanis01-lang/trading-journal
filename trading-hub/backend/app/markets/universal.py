"""Universal market catalogue (§23).

A strategy references *universal* markets (EURUSD, NASDAQ100, ...), never a
broker's symbol. Each universal market carries known aliases and descriptive
keywords used by the mapping engine. This is seed data; the user can add more.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..core.enums import AssetClass


@dataclass(slots=True)
class UniversalDef:
    symbol: str
    description: str
    asset_class: AssetClass
    base: str | None = None
    quote: str | None = None
    aliases: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


DEFAULT_UNIVERSAL: list[UniversalDef] = [
    UniversalDef("EURUSD", "Euro vs US Dollar", AssetClass.FOREX, "EUR", "USD",
                 ["EURUSD"], ["euro", "dollar"]),
    UniversalDef("GBPUSD", "British Pound vs US Dollar", AssetClass.FOREX, "GBP", "USD",
                 ["GBPUSD", "STERLING"], ["pound", "sterling", "dollar"]),
    UniversalDef("USDJPY", "US Dollar vs Japanese Yen", AssetClass.FOREX, "USD", "JPY",
                 ["USDJPY"], ["dollar", "yen"]),
    UniversalDef("XAUUSD", "Gold vs US Dollar", AssetClass.METAL, "XAU", "USD",
                 ["XAUUSD", "GOLD"], ["gold"]),
    UniversalDef("NASDAQ100", "US Tech 100 index", AssetClass.INDEX, "USD", "USD",
                 ["NASDAQ100", "USTEC", "NAS100", "US100", "NDX", "NQ", "USTECH"],
                 ["nasdaq", "tech", "100", "ustec"]),
    UniversalDef("US30", "Wall Street 30 / Dow Jones index", AssetClass.INDEX, "USD", "USD",
                 ["US30", "DJ30", "WS30", "DJIA", "YM", "DOWJONES", "DOW"],
                 ["dow", "jones", "wall", "street", "30"]),
    UniversalDef("BTCUSD", "Bitcoin vs US Dollar", AssetClass.CRYPTO, "BTC", "USD",
                 ["BTCUSD", "BITCOIN"], ["bitcoin", "btc"]),
]


def default_catalogue() -> list[UniversalDef]:
    return list(DEFAULT_UNIVERSAL)
