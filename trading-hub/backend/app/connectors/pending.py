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


# cTrader, Tradovate, NinjaTrader, Rithmic, DXtrade, Match-Trader, TradeLocker and
# Quantower now have real connectors under app/connectors/<key>/ and are registered
# directly in registry.py. Only MT4 remains a scaffold here (file-bridge EA).
ALL: list[type[_PendingConnector]] = [
    MT4Connector,
]
