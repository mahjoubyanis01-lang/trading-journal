"""DXtrade connector (§8, §88) - CFD/FX, REST.

DXtrade (Devexperts) brokers expose a REST/push API. Auth is a POST to
``/api/auth/login`` with ``{username, password, domain}`` returning a
``sessionToken``; authenticated calls carry ``Authorization: DXAPI <token>``.
Accounts and instruments are then GETs. The ``domain`` (broker realm) is an extra
credential; the API base URL comes from ``server``. No Expert-Advisor model, so
reads only.

Implemented against the documented DXtrade REST endpoints; not yet verified
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


class DXtradeConnector(BaseRestConnector):
    key = "dxtrade"
    display_name = "DXtrade"
    default_base_url = None  # broker specific -> needs_server() True

    @classmethod
    def requirement(cls) -> str:
        return (
            "DXtrade REST credentials: login = username, password, and the broker API "
            "base URL as `server`. The broker realm goes in the extra `domain` field. "
            "Authenticated with `Authorization: DXAPI <sessionToken>`; reads accounts "
            "and instruments. No robot lifecycle. "
            "Implemented; not yet verified against a live account."
        )

    @classmethod
    def extra_credential_fields(cls) -> list[CredentialField]:
        return [
            CredentialField("domain", "Domain / broker realm", secret=False, required=True),
        ]

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"DXAPI {self._token}"} if self._token else {}

    # --- hooks -----------------------------------------------------------
    def _login(self, client: httpx.Client, login: str, password: str,
               extra: dict[str, str]) -> str:
        resp = client.post("/api/auth/login", json={
            "username": login,
            "password": password,
            "domain": extra.get("domain", ""),
        })
        resp.raise_for_status()
        # Token may be in the body or in the Authorization/cookie on the response.
        data = resp.json() if resp.content else {}
        token = (data.get("sessionToken") or data.get("token")
                 or resp.headers.get("Authorization", "").replace("DXAPI ", "").strip()
                 or resp.cookies.get("JSESSIONID"))
        if not token:
            raise RuntimeError("DXtrade auth returned no session token")
        return token

    def _fetch_account(self, client: httpx.Client) -> AccountInfo:
        accounts = _as_list(client.get("/api/accounts").json())
        acct = accounts[0] if accounts else {}
        bal = acct.get("balances") if isinstance(acct.get("balances"), dict) else acct
        return AccountInfo(
            login=str(acct.get("account") or acct.get("accountId") or acct.get("id") or "0"),
            balance=round(_num(bal.get("balance")) or 0.0, 2),
            equity=round(_num(bal.get("equity")) or _num(bal.get("balance")) or 0.0, 2),
            currency=acct.get("currency") or bal.get("currency") or "USD",
            server=str(self._base_url or ""),
            broker="DXtrade",
        )

    def _fetch_instruments(self, client: httpx.Client) -> list[InstrumentInfo]:
        data = client.get("/api/instruments").json()
        out: list[InstrumentInfo] = []
        for ins in _as_list(data, "instruments"):
            sym = ins.get("symbol") or ins.get("name")
            if not sym:
                continue
            out.append(InstrumentInfo(
                symbol=sym,
                description=ins.get("description") or ins.get("longName"),
                tick_size=_num(ins.get("tickSize") or ins.get("minIncrement")),
                contract_size=_num(ins.get("contractSize") or ins.get("multiplier")),
                digits=_int(ins.get("precision") or ins.get("decimals")),
            ))
        return out

    def _fetch_positions(self, client: httpx.Client) -> list[PositionInfo]:
        try:
            data = client.get("/api/positions").json()
        except httpx.HTTPError:
            return []
        out: list[PositionInfo] = []
        for pos in _as_list(data, "positions"):
            qty = _num(pos.get("quantity")) or _num(pos.get("qty")) or 0.0
            if not qty:
                continue
            out.append(PositionInfo(
                symbol=str(pos.get("symbol") or pos.get("instrument") or ""),
                volume=abs(qty),
                direction="buy" if qty > 0 else "sell",
                open_price=_num(pos.get("openPrice") or pos.get("price")) or 0.0,
            ))
        return out


def _as_list(data: object, key: str | None = None) -> list[dict]:
    if isinstance(data, dict) and key and isinstance(data.get(key), list):
        data = data[key]
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
