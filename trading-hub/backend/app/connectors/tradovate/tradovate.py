"""Tradovate connector (§8, §88) - futures, REST + WebSocket.

Tradovate exposes a documented HTTPS API (https://api.tradovate.com/). Auth is a
POST to ``/auth/accesstokenrequest`` returning a bearer ``accessToken``; account,
cash balance, products (instruments) and positions are then simple GETs. There is
no Expert-Advisor model on Tradovate - algos run as the user's own API clients -
so this connector declares reads only (inherited from ``BaseRestConnector``).

The live and demo deployments have distinct hosts; ``server`` chooses between
them ("live"/"demo", or a full base URL), defaulting to demo.

Implemented against the documented Tradovate REST endpoints; not yet verified
against a live account.
"""
from __future__ import annotations

import httpx

from ...core.enums import AssetClass
from ..base import (
    AccountInfo,
    ConnectResult,
    CredentialField,
    InstrumentInfo,
    PositionInfo,
)
from ..rest_base import BaseRestConnector

LIVE_URL = "https://live.tradovateapi.com/v1"
DEMO_URL = "https://demo.tradovateapi.com/v1"


class TradovateConnector(BaseRestConnector):
    key = "tradovate"
    display_name = "Tradovate"
    # Sensible default so needs_server() is False; ``server`` may still override.
    default_base_url = DEMO_URL

    def __init__(self) -> None:
        super().__init__()
        self._account_id: int | None = None

    @classmethod
    def requirement(cls) -> str:
        return (
            "Tradovate API credentials: username/password plus an API application "
            "(app_id, app_version, cid, sec) and a device_id. REST host is chosen by "
            "`server` ('live'/'demo' or a full https base URL; default demo). "
            "Reads account, cash balance, products and positions (futures); no robot "
            "lifecycle (algos are the user's own API clients). "
            "Implemented; not yet verified against a live account."
        )

    @classmethod
    def extra_credential_fields(cls) -> list[CredentialField]:
        return [
            CredentialField("app_id", "Application ID (appId)", secret=False, required=True),
            CredentialField("app_version", "Application version", secret=False, required=False),
            CredentialField("cid", "API key id (cid)", secret=False, required=True),
            CredentialField("sec", "API key secret (sec)", secret=True, required=True),
            CredentialField("device_id", "Device ID", secret=False, required=True),
        ]

    # Translate a friendly ``server`` ("live"/"demo") into a full base URL.
    def connect(self, login: str, password: str, server: str | None = None,
                extra: dict[str, str] | None = None) -> ConnectResult:
        return super().connect(login, password, self._resolve_base(server), extra)

    def _resolve_base(self, server: str | None) -> str:
        if not server:
            return self.default_base_url
        s = server.strip().lower()
        if s in ("demo", "demo account"):
            return DEMO_URL
        if s in ("live", "prod", "production"):
            return LIVE_URL
        return server

    # --- hooks -----------------------------------------------------------
    def _login(self, client: httpx.Client, login: str, password: str,
               extra: dict[str, str]) -> str:
        body = {
            "name": login,
            "password": password,
            "appId": extra.get("app_id", ""),
            "appVersion": extra.get("app_version") or "1.0",
            "cid": extra.get("cid", ""),
            "sec": extra.get("sec", ""),
            "deviceId": extra.get("device_id", ""),
        }
        resp = client.post("/auth/accesstokenrequest", json=body)
        resp.raise_for_status()
        data = resp.json()
        token = data.get("accessToken")
        if not token:
            raise RuntimeError(data.get("errorText") or "Tradovate auth returned no accessToken")
        return token

    def _fetch_account(self, client: httpx.Client) -> AccountInfo:
        accounts = _as_list(client.get("/account/list").json())
        acct = accounts[0] if accounts else {}
        self._account_id = acct.get("id")
        balance = equity = 0.0
        # Cash balance snapshot is best-effort: keep the account readable even if
        # this endpoint is unavailable for the deployment.
        if self._account_id is not None:
            try:
                snap = client.post(
                    "/cashBalance/getcashbalancesnapshot",
                    json={"accountId": self._account_id},
                ).json()
                balance = _num(snap.get("totalCashValue")) or _num(snap.get("totalPnL")) or 0.0
                equity = _num(snap.get("netLiq")) or balance
            except (httpx.HTTPError, ValueError, TypeError):
                pass
        return AccountInfo(
            login=str(acct.get("id") or acct.get("name") or "0"),
            balance=round(balance, 2),
            equity=round(equity, 2),
            currency=acct.get("currency") or "USD",
            server=str(self._base_url or ""),
            broker="Tradovate",
        )

    def _fetch_instruments(self, client: httpx.Client) -> list[InstrumentInfo]:
        out: list[InstrumentInfo] = []
        for p in _as_list(client.get("/product/list").json()):
            name = p.get("name")
            if not name:
                continue
            out.append(InstrumentInfo(
                symbol=name,
                description=p.get("description"),
                asset_class=AssetClass.FUTURE,
                tick_size=_num(p.get("tickSize")),
                contract_size=_num(p.get("valuePerPoint")),
            ))
        return out

    def _fetch_positions(self, client: httpx.Client) -> list[PositionInfo]:
        out: list[PositionInfo] = []
        for p in _as_list(client.get("/position/list").json()):
            net = _num(p.get("netPos")) or 0.0
            if not net:
                continue
            out.append(PositionInfo(
                symbol=str(p.get("contractId") or ""),
                volume=abs(net),
                direction="buy" if net > 0 else "sell",
                open_price=_num(p.get("netPrice")) or 0.0,
            ))
        return out


def _as_list(data: object) -> list[dict]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [x for x in data["items"] if isinstance(x, dict)]
    return []


def _num(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
