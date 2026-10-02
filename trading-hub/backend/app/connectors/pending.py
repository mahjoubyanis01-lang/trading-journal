"""Honest connector scaffolds for platforms beyond MT5 (§8, §88, §95).

The spec is explicit: do NOT fake an integration. For each additional platform
we register a real connector that declares *no* capabilities yet and states
exactly what it needs / how it will integrate. The UI lists it truthfully
(available=false + a requirement note) instead of pretending it works. Filling
one in later is a self-contained change - no core edits (§8).

MetaTrader 5 (and the MT4 file-bridge EA) are the fully-built connectors; these
are the documented next steps.
"""
from __future__ import annotations

from .base import PlatformCapabilities, PlatformConnector


class _PendingConnector(PlatformConnector):
    """Declares nothing it cannot truly do. Connecting raises a clear error."""

    _requirement = "integration pending"

    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities()  # all False - honest (§88)

    @classmethod
    def requirement(cls) -> str:
        return cls._requirement


class MT4Connector(_PendingConnector):
    key = "mt4"
    display_name = "MetaTrader 4"
    _requirement = (
        "Windows + MetaTrader 4. No official Python API; integrates via the "
        "provided MQL4 bridge EA (assets/mt4/TradingHubBridge.mq4) for "
        "heartbeat/account/RUN-STOP, like MT5."
    )


class CTraderConnector(_PendingConnector):
    key = "ctrader"
    display_name = "cTrader"
    _requirement = (
        "cTrader Open API credentials (OAuth app clientId/secret). Protobuf over "
        "TCP; reads account/symbols/positions. No EA model - robots run as cBots."
    )


class TradovateConnector(_PendingConnector):
    key = "tradovate"
    display_name = "Tradovate"
    _requirement = (
        "Tradovate API access (username/password/app id/secret, device id). "
        "REST + WebSocket; reads account/positions/instruments (futures)."
    )


class NinjaTraderConnector(_PendingConnector):
    key = "ninjatrader"
    display_name = "NinjaTrader"
    _requirement = (
        "Windows + NinjaTrader 8 with ATI/NTDirect enabled, or the socket API. "
        "Robots are NinjaScript strategies managed in-platform."
    )


class RithmicConnector(_PendingConnector):
    key = "rithmic"
    display_name = "Rithmic"
    _requirement = "Rithmic R|API+ credentials and gateway access (futures)."


class DXtradeConnector(_PendingConnector):
    key = "dxtrade"
    display_name = "DXtrade"
    _requirement = "DXtrade REST/WebSocket broker credentials and API endpoint."


class MatchTraderConnector(_PendingConnector):
    key = "matchtrader"
    display_name = "Match-Trader"
    _requirement = "Match-Trader broker API credentials and endpoint."


class TradeLockerConnector(_PendingConnector):
    key = "tradelocker"
    display_name = "TradeLocker"
    _requirement = "TradeLocker REST API credentials (email/password/server)."


class QuantowerConnector(_PendingConnector):
    key = "quantower"
    display_name = "Quantower"
    _requirement = "Quantower API / plugin bridge on the host machine."


ALL: list[type[_PendingConnector]] = [
    MT4Connector, CTraderConnector, TradovateConnector, NinjaTraderConnector,
    RithmicConnector, DXtradeConnector, MatchTraderConnector,
    TradeLockerConnector, QuantowerConnector,
]
