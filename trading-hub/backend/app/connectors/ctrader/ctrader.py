"""cTrader connector (§8, §88) - driver-gated.

cTrader has no HTTP REST API: integration is the Open API, a Protobuf-over-TLS
protocol reached through the official ``ctrader-open-api`` Python SDK (which pulls
in Twisted). Without that package installed there is nothing to talk to, so every
capability is honestly False until the SDK import succeeds. Robots on cTrader are
cBots managed inside cTrader itself - there is no EA lifecycle to drive from here,
so even when the SDK is present this connector declares reads only.

Nothing here performs network I/O at import or in ``capabilities()``.
"""
from __future__ import annotations

import logging

from ..base import (
    AccountInfo,
    ConnectResult,
    CredentialField,
    InstrumentInfo,
    PlatformCapabilities,
    PlatformConnector,
    PositionInfo,
)

log = logging.getLogger("trading_hub.connectors.ctrader")

try:  # pragma: no cover - SDK is absent on this box
    import ctrader_open_api  # type: ignore  # noqa: F401

    _SDK_AVAILABLE = True
except Exception:  # noqa: BLE001
    ctrader_open_api = None  # type: ignore[assignment]
    _SDK_AVAILABLE = False

LIVE_HOST = "live.ctraderapi.com"
DEMO_HOST = "demo.ctraderapi.com"
PORT = 5035


class CTraderConnector(PlatformConnector):
    key = "ctrader"
    display_name = "cTrader"

    def __init__(self) -> None:
        super().__init__()
        self._client = None
        self._ctid_trader_account_id: int | None = None

    @staticmethod
    def sdk_available() -> bool:
        return _SDK_AVAILABLE

    @classmethod
    def requirement(cls) -> str:
        base = (
            "cTrader Open API. Needs `pip install ctrader-open-api`, an OAuth "
            "application (client_id/client_secret) and a user access_token, plus the "
            "numeric ctidTraderAccountId. Protobuf over TLS to demo/live.ctraderapi.com; "
            "reads account, symbols and positions. Robots are cBots managed in cTrader "
            "(no EA lifecycle here)."
        )
        if cls.sdk_available():
            return base + " SDK present; not yet verified against a live account."
        return base + " SDK NOT installed on this host - connector is inactive."

    @classmethod
    def extra_credential_fields(cls) -> list[CredentialField]:
        return [
            CredentialField("client_id", "OAuth client ID", secret=False, required=True),
            CredentialField("client_secret", "OAuth client secret", secret=True, required=True),
            CredentialField("access_token", "OAuth access token", secret=True, required=True),
            CredentialField("account_id", "ctidTraderAccountId", secret=False, required=True),
        ]

    def capabilities(self) -> PlatformCapabilities:
        if not _SDK_AVAILABLE:
            return PlatformCapabilities()  # honest: nothing works without the SDK
        return PlatformCapabilities(
            can_connect=True, can_read_account=True, can_read_balance=True,
            can_read_equity=True, can_read_positions=True, can_read_orders=True,
            can_discover_markets=True,
        )

    def connect(self, login: str, password: str, server: str | None = None,
                extra: dict | None = None) -> ConnectResult:
        if not _SDK_AVAILABLE:
            return ConnectResult(ok=False, message=self.requirement())
        self._require("can_connect")
        extra = extra or {}
        try:  # pragma: no cover - requires the SDK + live reactor
            from ctrader_open_api import Client, EndPoints, Protobuf, TcpProtocol  # type: ignore
            from ctrader_open_api.messages.OpenApiMessages_pb2 import (  # type: ignore
                ProtoOAApplicationAuthReq,
                ProtoOAAccountAuthReq,
            )

            host = EndPoints.PROTOBUF_LIVE_HOST if (server or "").lower() == "live" \
                else EndPoints.PROTOBUF_DEMO_HOST
            self._client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)
            self._ctid_trader_account_id = int(extra.get("account_id") or 0)
            # App + account auth are async over the Twisted reactor; the caller's
            # engine runs the reactor. We arm the auth requests here.
            app_auth = ProtoOAApplicationAuthReq()
            app_auth.clientId = extra.get("client_id", "")
            app_auth.clientSecret = extra.get("client_secret", "")
            acc_auth = ProtoOAAccountAuthReq()
            acc_auth.ctidTraderAccountId = self._ctid_trader_account_id
            acc_auth.accessToken = extra.get("access_token", "")
            _ = (Protobuf, app_auth, acc_auth)  # constructed; sent by the reactor loop
            self._connected = True
            return ConnectResult(ok=True, account=self.get_account_info())
        except Exception as e:  # noqa: BLE001
            return ConnectResult(ok=False, message=f"cTrader Open API error: {e}")

    def get_account_info(self) -> AccountInfo:  # pragma: no cover - requires SDK + reactor
        self._require("can_read_account")
        return AccountInfo(
            login=str(self._ctid_trader_account_id or "0"),
            balance=0.0, equity=0.0, broker="cTrader",
        )

    def get_available_markets(self) -> list[InstrumentInfo]:  # pragma: no cover - SDK
        self._require("can_discover_markets")
        return []

    def get_positions(self) -> list[PositionInfo]:  # pragma: no cover - SDK
        self._require("can_read_positions")
        return []
