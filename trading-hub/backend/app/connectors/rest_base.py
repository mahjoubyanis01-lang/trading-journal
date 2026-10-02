"""Base for HTTP/REST broker connectors (§8).

Many modern platforms (Tradovate, TradeLocker, DXtrade, Match-Trader, ...)
expose an HTTPS/WebSocket API. This base turns one into a Trading Hub connector
by implementing the plumbing (session, auth header, error handling) and leaving
four small hooks for the subclass.

Honesty (§88): these brokers have no "Expert Advisor" to launch, so robot
lifecycle capabilities stay False. Trading Hub reads the account, discovers
instruments, sizes risk and monitors positions; the user's algo connects to the
same broker API itself. Each subclass states its verification status in
``requirement()``. Nothing here performs network I/O at import or in
``capabilities()`` - only ``connect()`` touches the network.
"""
from __future__ import annotations

import logging

import httpx

from .base import (
    AccountInfo,
    ConnectResult,
    InstrumentInfo,
    PlatformCapabilities,
    PlatformConnector,
    PositionInfo,
)

log = logging.getLogger("trading_hub.connectors.rest")


class BaseRestConnector(PlatformConnector):
    default_base_url: str | None = None
    timeout_s: float = 15.0

    def __init__(self) -> None:
        super().__init__()
        self._client: httpx.Client | None = None
        self._token: str | None = None
        self._base_url: str | None = None

    def capabilities(self) -> PlatformCapabilities:
        # Reads only; no EA/robot lifecycle on a broker API (honest, §88).
        return PlatformCapabilities(
            can_connect=True, can_read_account=True, can_read_balance=True,
            can_read_equity=True, can_read_positions=True, can_read_orders=True,
            can_discover_markets=True,
        )

    @classmethod
    def needs_server(cls) -> bool:
        return cls.default_base_url is None

    # --- subclass hooks --------------------------------------------------
    def _login(self, client: httpx.Client, login: str, password: str,
               extra: dict[str, str]) -> str:
        """Authenticate; return a bearer token (or session id). Raise on failure."""
        raise NotImplementedError

    def _fetch_account(self, client: httpx.Client) -> AccountInfo:
        raise NotImplementedError

    def _fetch_instruments(self, client: httpx.Client) -> list[InstrumentInfo]:
        return []

    def _fetch_positions(self, client: httpx.Client) -> list[PositionInfo]:
        return []

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    # --- lifecycle -------------------------------------------------------
    def connect(self, login: str, password: str, server: str | None = None,
                extra: dict[str, str] | None = None) -> ConnectResult:
        self._require("can_connect")
        extra = extra or {}
        self._base_url = (server or self.default_base_url or "").rstrip("/")
        if not self._base_url:
            return ConnectResult(ok=False, message="A server/API endpoint is required")
        try:
            self._client = httpx.Client(base_url=self._base_url, timeout=self.timeout_s)
            self._token = self._login(self._client, login, password, extra)
            if self._token:
                self._client.headers.update(self._auth_headers())
            self._connected = True
            return ConnectResult(ok=True, account=self.get_account_info())
        except httpx.HTTPError as e:
            return ConnectResult(ok=False, message=f"HTTP error: {e}")
        except Exception as e:  # noqa: BLE001
            return ConnectResult(ok=False, message=str(e))

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._connected = False

    def get_account_info(self) -> AccountInfo:
        self._require("can_read_account")
        assert self._client is not None
        return self._fetch_account(self._client)

    def get_available_markets(self) -> list[InstrumentInfo]:
        self._require("can_discover_markets")
        assert self._client is not None
        return self._fetch_instruments(self._client)

    def get_positions(self) -> list[PositionInfo]:
        self._require("can_read_positions")
        assert self._client is not None
        return self._fetch_positions(self._client)

    def account_alive(self) -> bool:
        return self._connected and self._client is not None
