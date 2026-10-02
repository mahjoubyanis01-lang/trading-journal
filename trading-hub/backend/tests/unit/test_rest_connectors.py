"""Offline tests for REST connector auth handling.

These encode behaviours verified LIVE against the brokers' demo endpoints
(no network here — httpx MockTransport replays the real response shapes):
  - Tradovate returns HTTP 200 with {"errorText": ...} on auth failure, so the
    connector must inspect the body, not the status code.
  - TradeLocker returns HTTP 4xx with {"message": ...} and we surface it.
"""
from __future__ import annotations

import httpx
import pytest

from app.connectors.tradelocker.tradelocker import TradeLockerConnector
from app.connectors.tradovate.tradovate import TradovateConnector


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://demo.example")


# --- Tradovate: 200 + errorText means failure (verified live) ---
def test_tradovate_login_rejects_200_errortext():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errorText": "Incorrect username or password."})

    c = TradovateConnector()
    with pytest.raises(RuntimeError, match="Incorrect username or password"):
        c._login(_client(handler), "u", "p", {"app_id": "a", "cid": "1", "sec": "s", "device_id": "d"})


def test_tradovate_login_success_returns_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"accessToken": "TOK123", "userId": 1})

    c = TradovateConnector()
    assert c._login(_client(handler), "u", "p", {"app_id": "a", "cid": "1", "sec": "s", "device_id": "d"}) == "TOK123"


# --- TradeLocker: 4xx + message surfaced (verified live) ---
def test_tradelocker_login_surfaces_server_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Failed to fetch token, check if server exists"})

    c = TradeLockerConnector()
    with pytest.raises(RuntimeError, match="check if server exists"):
        c._login(_client(handler), "e@x.com", "p", {"tl_server": "BAD"})


def test_tradelocker_login_success():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"accessToken": "JWT"})
        if request.url.path.endswith("/all-accounts"):
            return httpx.Response(200, json={"accounts": [{"id": "7", "accNum": "1"}]})
        return httpx.Response(404)

    c = TradeLockerConnector()
    assert c._login(_client(handler), "e@x.com", "p", {"tl_server": "OSP-DEMO"}) == "JWT"
    assert c._acc_id == "7"
