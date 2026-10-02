"""Match-Trader connector (§8, §88) - CFD/FX, REST.

Match-Trader (Match-Trade Technologies) exposes a broker REST API. The trader
endpoints live under ``/mtr-api/{system_uuid}/``. Login is a POST to
``/mtr-api/{system_uuid}/login`` with ``{email, password}`` returning a token
(body ``token`` and/or an ``Auth-token`` response header); authenticated calls
carry the ``Auth-token`` header. Account balance and instruments are then GETs.
The ``system_uuid`` (broker system id) is an extra credential; the API base URL
comes from ``server``. No Expert-Advisor model, so reads only.

Implemented against the documented Match-Trader REST endpoints; not yet verified
against a live account.
"""
from __future__ import annotations

import httpx

from ..base import (
    AccountInfo,
    CredentialField,
    InstrumentInfo,
    PositionInfo,
)
from ..rest_base import BaseRestConnector


class MatchTraderConnector(BaseRestConnector):
    key = "matchtrader"
    display_name = "Match-Trader"
    default_base_url = None  # broker specific -> needs_server() True

    def __init__(self) -> None:
        super().__init__()
        self._system_uuid: str = ""

    @classmethod
    def requirement(cls) -> str:
        return (
            "Match-Trader broker REST credentials: login = account email, password, "
            "and the broker API base URL as `server`. The broker `system_uuid` goes in "
            "the extra field. Authenticated with the `Auth-token` header; reads account "
            "balance and instruments. No robot lifecycle. "
            "Implemented; not yet verified against a live account."
        )

    @classmethod
    def extra_credential_fields(cls) -> list[CredentialField]:
        return [
            CredentialField("system_uuid", "System UUID", secret=False, required=True),
        ]

    def _auth_headers(self) -> dict[str, str]:
        return {"Auth-token": self._token} if self._token else {}

    def _base(self) -> str:
        return f"/mtr-api/{self._system_uuid}"

    # --- hooks -----------------------------------------------------------
    def _login(self, client: httpx.Client, login: str, password: str,
               extra: dict[str, str]) -> str:
        self._system_uuid = extra.get("system_uuid", "")
        resp = client.post(f"{self._base()}/login", json={
            "email": login,
            "password": password,
        })
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        token = (data.get("token") or data.get("tradingApiToken")
                 or resp.headers.get("Auth-token"))
        if not token:
            raise RuntimeError("Match-Trader login returned no token")
        return token

    def _fetch_account(self, client: httpx.Client) -> AccountInfo:
        data = client.get(f"{self._base()}/balance").json()
        d = data if isinstance(data, dict) else {}
        return AccountInfo(
            login=str(d.get("accountId") or d.get("login") or "0"),
            balance=round(_num(d.get("balance")) or 0.0, 2),
            equity=round(_num(d.get("equity")) or _num(d.get("balance")) or 0.0, 2),
            currency=d.get("currency") or "USD",
            server=str(self._base_url or ""),
            broker="Match-Trader",
        )

    def _fetch_instruments(self, client: httpx.Client) -> list[InstrumentInfo]:
        data = client.get(f"{self._base()}/instruments").json()
        out: list[InstrumentInfo] = []
        for ins in _as_list(data, "instruments", "symbols"):
            sym = ins.get("symbol") or ins.get("name")
            if not sym:
                continue
            out.append(InstrumentInfo(
                symbol=sym,
                description=ins.get("description") or ins.get("displayName"),
                tick_size=_num(ins.get("tickSize") or ins.get("step")),
                contract_size=_num(ins.get("contractSize") or ins.get("lotSize")),
                digits=_int(ins.get("precision") or ins.get("digits")),
            ))
        return out

    def _fetch_positions(self, client: httpx.Client) -> list[PositionInfo]:
        try:
            data = client.get(f"{self._base()}/positions").json()
        except httpx.HTTPError:
            return []
        out: list[PositionInfo] = []
        for pos in _as_list(data, "positions"):
            vol = _num(pos.get("volume")) or _num(pos.get("lots")) or 0.0
            if not vol:
                continue
            side = str(pos.get("side") or pos.get("type") or "").lower()
            out.append(PositionInfo(
                symbol=str(pos.get("symbol") or ""),
                volume=abs(vol),
                direction="sell" if side.startswith("s") else "buy",
                open_price=_num(pos.get("openPrice") or pos.get("price")) or 0.0,
            ))
        return out


def _as_list(data: object, *keys: str) -> list[dict]:
    if isinstance(data, dict):
        for key in keys:
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _num(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _int(v: object) -> int | None:
    n = _num(v)
    return int(n) if n is not None else None
