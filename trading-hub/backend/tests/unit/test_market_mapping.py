"""Market mapping + confidence tests (§25-28, Acceptance Test 4)."""
from app.connectors.base import InstrumentInfo
from app.core.enums import AssetClass, MappingStatus
from app.markets.mapping import MarketMappingEngine
from app.markets.universal import DEFAULT_UNIVERSAL

ENGINE = MarketMappingEngine(auto=90.0, confirm=70.0)
BY_SYMBOL = {u.symbol: u for u in DEFAULT_UNIVERSAL}

# A broker instrument set mirroring the mock world.
INSTRUMENTS = [
    InstrumentInfo("EURUSDm", "Euro vs US Dollar", AssetClass.FOREX, "EUR", "USD"),
    InstrumentInfo("GOLD", "Gold vs US Dollar", AssetClass.METAL, "XAU", "USD"),
    InstrumentInfo("USTEC", "US Tech 100 index", AssetClass.INDEX, "USD", "USD"),
    InstrumentInfo("DJ30", "Wall Street 30 index", AssetClass.INDEX, "USD", "USD"),
]


def test_exact_with_broker_suffix_is_high_confidence():
    best, status = ENGINE.resolve(BY_SYMBOL["EURUSD"], INSTRUMENTS)
    assert best.real_symbol == "EURUSDm"
    assert best.confidence >= 90
    assert status == MappingStatus.AUTO


def test_alias_gold():
    best, status = ENGINE.resolve(BY_SYMBOL["XAUUSD"], INSTRUMENTS)
    assert best.real_symbol == "GOLD"
    assert best.confidence >= 90
    assert status == MappingStatus.AUTO


def test_alias_nasdaq_ustec():
    best, status = ENGINE.resolve(BY_SYMBOL["NASDAQ100"], INSTRUMENTS)
    assert best.real_symbol == "USTEC"
    assert status == MappingStatus.AUTO


def test_unresolved_when_no_signal():
    # A broker that only offers an unrelated instrument => no NASDAQ match.
    only = [InstrumentInfo("ZARJPY", "Rand vs Yen", AssetClass.FOREX, "ZAR", "JPY")]
    best, status = ENGINE.resolve(BY_SYMBOL["NASDAQ100"], only)
    assert status == MappingStatus.UNRESOLVED
    assert best is None or best.confidence < 70


def test_candidates_ranked_for_search_ui():
    # §28 : offer ranked alternatives for NASDAQ100
    universe = INSTRUMENTS + [
        InstrumentInfo("NAS100.cash", "Nasdaq 100 Cash", AssetClass.INDEX, "USD", "USD"),
        InstrumentInfo("NQ", "E-mini Nasdaq 100", AssetClass.FUTURE, "USD", "USD"),
    ]
    cands = ENGINE.candidates(BY_SYMBOL["NASDAQ100"], universe)
    syms = [c.real_symbol for c in cands]
    assert "USTEC" in syms and "NAS100.cash" in syms
    # sorted descending by confidence
    confs = [c.confidence for c in cands]
    assert confs == sorted(confs, reverse=True)


def test_confidence_thresholds_configurable():
    strict = MarketMappingEngine(auto=99.0, confirm=95.0)
    best, status = strict.resolve(BY_SYMBOL["NASDAQ100"], INSTRUMENTS)
    # USTEC alias ~93-95 -> below strict auto threshold now
    assert status in (MappingStatus.NEEDS_CONFIRMATION, MappingStatus.UNRESOLVED)
