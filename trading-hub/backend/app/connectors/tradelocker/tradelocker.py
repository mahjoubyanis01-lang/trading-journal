"""TradeLocker connector (§8, §88) - CFD/FX, REST.

TradeLocker publishes a documented REST API (https://tradelocker.com/api). Auth is
a POST to ``/backend-api/auth/jwt/token`` with ``{email, password, server}``
returning an ``accessToken``; ``/backend-api/auth/jwt/all-accounts`` then lists the
user's accounts. Per-account reads (``/trade/accounts/{id}/state`` and
``/trade/accounts/{id}/instruments``) require both the bearer token and an
``accNum`` header.

The API base URL is broker/environment specific and comes from ``server``
(e.g. https://demo.tradelocker.com). The ``server`` *field* inside the JWT body
(the broker environment name, e.g. "OSP-DEMO") is a separate extra credential.
No Expert-Advisor model, so reads only.

Implemented against the documented TradeLocker REST endpoints; not yet verified
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


class TradeLockerConnector(BaseRestConnector):
    key = "tradelocker"
    display_name = "TradeLocker"
    default_base_url = None  # broker specific -> needs_server() True

    def __init__(self) -> None:
        super().__init__()
        self._acc_id: str | None = None
        self._acc_num: str | None = None

    @classmethod
    def requirement(cls) -> str:
        return (
            "TradeLocker REST credentials: login = account email, password, and the "
            "broker API base URL as `server` (e.g. https://demo.tradelocker.com). The "
            "broker environment name goes in the extra `tl_server` field; `account_id` "
            "is optional (first account is used otherwise). Reads account state and "
            "instruments; no robot lifecycle. "
            "Implemented; not yet verified against a live account."
        )

    @classmethod
    def extra_credential_fields(cls) -> list[CredentialField]:
        return [
            CredentialField("tl_server", "Broker environment (server)", secret=False, required=True),
            CredentialField("account_id", "Account ID (optional)", secret=False, required=False),
        ]

    def _auth_headers(self) -> dict[str, str]:
        headers = super()._auth_headers()
        if self._acc_num:
            headers["accNum"] = str(self._acc_num)
        return headers

    # --- hooks -----------------------------------------------------------
    def _login(self, client: httpx.Client, login: str, password: str,
               extra: dict[str, str]) -> str:
        resp = client.post("/backend-api/auth/jwt/token", json={
            "email": login,
            "password": password,
            "server": extra.get("tl_server", ""),
        })
        # TradeLocker returns 4xx + {"message": "..."} on failure (verified live);
        # surface that message rather than a generic HTTP error.
        if resp.status_code >= 400:
            try:
                msg = resp.json().get("message")
            except ValueError:
                msg = None
            raise RuntimeError(msg or f"TradeLocker auth failed (HTTP {resp.status_code})")
        token = resp.json().get("accessToken")
        if not token:
            raise RuntimeError("TradeLocker auth returned no accessToken")
        # all-accounts needs the bearer; set it before the call.
        self._token = token
        accounts = _as_list(client.get(
            "/backend-api/auth/jwt/all-accounts",
            headers={"Authorization": f"Bearer {token}"},
        ).json(), "accounts")
        want = extra.get("account_id")
        acct = _pick(accounts, want)
        if acct:
            self._acc_id = str(acct.get("id") or acct.get("accountId") or "")
            self._acc_num = str(acct.get("accNum") or acct.get("accountNum") or "")
        return token

    def _fetch_account(self, client: httpx.Client) -> AccountInfo:
        balance = equity = 0.0
        currency = "USD"
        if self._acc_id:
            try:
                state = client.get(f"/backend-api/trade/accounts/{self._acc_id}/state").json()
                d = state.get("d", state) if isinstance(state, dict) else {}
                details = d.get("accountDetailsData")
                # accountDetailsData is a positional array; also try named forms.
                balance = _num(d.get("balance")) or _first_num(details) or 0.0
                equity = _num(d.get("projectedBalance")) or _num(d.get("equity")) or balance
                currency = d.get("currency") or currency
            except (httpx.HTTPError, ValueError, TypeError):
                pass
        return AccountInfo(
            login=str(self._acc_id or "0"),
            balance=round(balance, 2),
            equity=round(equity, 2),
            currency=currency,
            server=str(self._base_url or ""),
            broker="TradeLocker",
        )

    def _fetch_instruments(self, client: httpx.Client) -> list[InstrumentInfo]:
        if not self._acc_id:
            return []
        data = client.get(f"/backend-api/trade/accounts/{self._acc_id}/instruments").json()
        d = data.get("d", data) if isinstance(data, dict) else {}
        out: list[InstrumentInfo] = []
        for ins in _as_list(d, "instruments"):
            name = ins.get("name") or ins.get("symbol")
            if not name:
                continue
            out.append(InstrumentInfo(
                symbol=name,
                description=ins.get("description"),
                tick_size=_num(ins.get("tickSize")),
                contract_size=_num(ins.get("contractSize")),
                digits=_int(ins.get("decimals") or ins.get("digits")),
            ))
        return out

    def _fetch_positions(self, client: httpx.Client) -> list[PositionInfo]:
        if not self._acc_id:
            return []
        try:
            data = client.get(f"/backend-api/trade/accounts/{self._acc_id}/positions").json()
        except httpx.HTTPError:
            return []
        d = data.get("d", data) if isinstance(data, dict) else {}
        out: list[PositionInfo] = []
        for pos in _as_list(d, "positions"):
            qty = _num(pos.get("qty")) or _num(pos.get("quantity")) or 0.0
            if not qty:
                continue
            side = str(pos.get("side") or ("buy" if qty > 0 else "sell")).lower()
            out.append(PositionInfo(
                symbol=str(pos.get("tradableInstrumentId") or pos.get("symbol") or ""),
                volume=abs(qty),
                direction="buy" if side.startswith("b") else "sell",
                open_price=_num(pos.get("avgPrice")) or _num(pos.get("openPrice")) or 0.0,
            ))
        return out


def _as_list(data: object, key: str | None = None) -> list[dict]:
    if isinstance(data, dict) and key and isinstance(data.get(key), list):
        data = data[key]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _pick(accounts: list[dict], want: str | None) -> dict | None:
    if not accounts:
        return None
    if want:
        for a in accounts:
            if str(a.get("id") or a.get("accountId") or "") == str(want):
                return a
    return accounts[0]


def _num(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _int(v: object) -> int | None:
    n = _num(v)
    return int(n) if n is not None else None


def _first_num(seq: object) -> float | None:
    if isinstance(seq, list):
        for item in seq:
            n = _num(item)
            if n is not None:
                return n
    return None
