"""NinjaTrader connector (§8, §88) - driver-gated (Windows only).

NinjaTrader 8 has no cross-platform API. The integration point is the ATI
(Automated Trading Interface): a local file drop (``Documents\\NinjaTrader 8\\
incoming``) and a TCP command socket (default 127.0.0.1:36973) served by NT8 when
"AT Interface" is enabled. It only exists on a Windows host running NinjaTrader,
so every capability is honestly False unless ``sys.platform == 'win32'``. Robots
are NinjaScript strategies managed inside NT8; there is no remote EA lifecycle, so
even on Windows this connector declares reads only (account value via ATI).

Nothing here performs I/O at import or in ``capabilities()``.
"""
from __future__ import annotations

import logging
import socket
import sys

from ..base import (
    AccountInfo,
    ConnectResult,
    CredentialField,
    InstrumentInfo,
    PlatformCapabilities,
    PlatformConnector,
    PositionInfo,
)

log = logging.getLogger("trading_hub.connectors.ninjatrader")

ATI_HOST = "127.0.0.1"
ATI_PORT = 36973


class NinjaTraderConnector(PlatformConnector):
    key = "ninjatrader"
    display_name = "NinjaTrader"

    def __init__(self) -> None:
        super().__init__()
        self._sock: socket.socket | None = None
        self._account = "Sim101"

    @staticmethod
    def runtime_available() -> bool:
        return sys.platform == "win32"

    @classmethod
    def requirement(cls) -> str:
        base = (
            "Windows + NinjaTrader 8 with the ATI (Automated Trading Interface) "
            "enabled. Reads account value via the ATI command socket "
            f"({ATI_HOST}:{ATI_PORT}) / the OIF file drop in "
            "'Documents\\NinjaTrader 8\\incoming'. Robots are NinjaScript strategies "
            "managed inside NT8 (no remote EA lifecycle). `login` = NT account name "
            "(e.g. Sim101)."
        )
        if cls.runtime_available():
            return base + " Running on Windows; not yet verified against a live NT8."
        return base + " Not a Windows host - connector is inactive."

    @classmethod
    def extra_credential_fields(cls) -> list[CredentialField]:
        return [
            CredentialField("ati_port", "ATI port", secret=False, required=False),
        ]

    def capabilities(self) -> PlatformCapabilities:
        if not self.runtime_available():
            return PlatformCapabilities()  # honest: no NT8/ATI off Windows
        return PlatformCapabilities(
            can_connect=True, can_read_account=True,
            can_read_balance=True, can_read_equity=True,
        )

    def connect(self, login: str, password: str, server: str | None = None,
                extra: dict | None = None) -> ConnectResult:
        if not self.runtime_available():
            return ConnectResult(ok=False, message=self.requirement())
        self._require("can_connect")
        extra = extra or {}
        port = int(extra.get("ati_port") or ATI_PORT)
        self._account = login or self._account
        try:  # pragma: no cover - requires Windows + running NT8
            self._sock = socket.create_connection((ATI_HOST, port), timeout=5.0)
            self._connected = True
            return ConnectResult(ok=True, account=self.get_account_info())
        except OSError as e:  # NT8 not running / ATI disabled
            return ConnectResult(ok=False, message=f"NinjaTrader ATI socket error: {e}")

    def disconnect(self) -> None:
        if self._sock is not None:  # pragma: no cover - Windows
            try:
                self._sock.close()
            finally:
                self._sock = None
        self._connected = False

    def get_account_info(self) -> AccountInfo:  # pragma: no cover - Windows + NT8
        self._require("can_read_account")
        balance = self._ati_account_value("CashValue")
        equity = self._ati_account_value("RealizedProfitLoss")
        return AccountInfo(
            login=self._account,
            balance=balance or 0.0,
            equity=(balance or 0.0) + (equity or 0.0),
            broker="NinjaTrader",
        )

    def _ati_account_value(self, name: str) -> float | None:  # pragma: no cover - Windows
        # ATI query: "ACCOUNTVALUE|<name>|<account>|" -> numeric reply.
        if self._sock is None:
            return None
        try:
            self._sock.sendall(f"ACCOUNTVALUE|{name}|{self._account}|\n".encode())
            reply = self._sock.recv(256).decode(errors="ignore").strip()
            return float(reply) if reply else None
        except (OSError, ValueError):
            return None

    def get_available_markets(self) -> list[InstrumentInfo]:  # pragma: no cover
        self._require("can_discover_markets")  # not supported -> CapabilityError
        return []

    def get_positions(self) -> list[PositionInfo]:  # pragma: no cover
        self._require("can_read_positions")  # not supported -> CapabilityError
        return []
