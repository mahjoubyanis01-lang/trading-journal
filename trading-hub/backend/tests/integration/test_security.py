"""Security / safety tests (local hardening, risk caps, kill-switch)."""
from __future__ import annotations

import importlib
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def token_client(monkeypatch):
    """A fresh app instance with the loopback API token ENABLED."""
    monkeypatch.setenv("TH_API_TOKEN", "test-secret-token")
    from app.core import config
    config.get_settings.cache_clear()
    import app.main as main
    importlib.reload(main)
    try:
        with TestClient(main.app) as c:
            yield c
    finally:
        monkeypatch.delenv("TH_API_TOKEN", raising=False)
        config.get_settings.cache_clear()
        importlib.reload(main)


def test_api_requires_token_when_enabled(token_client):
    # No token -> 401 on an API route
    assert token_client.get("/api/dashboard").status_code == 401
    # Wrong token -> 401
    assert token_client.get("/api/dashboard", headers={"x-th-token": "nope"}).status_code == 401
    # Correct token -> ok
    ok = token_client.get("/api/dashboard", headers={"x-th-token": "test-secret-token"})
    assert ok.status_code == 200
    # Health + SPA shell stay open (page can bootstrap and read the token)
    assert token_client.get("/health").status_code == 200
    assert token_client.get("/").status_code in (200, 404)  # 404 only if dist absent


# --- the following use the shared (token-less) app from the main test module ---
from app.main import app  # noqa: E402

client = TestClient(app)


def _seed_once():
    client.post("/api/seed-demo", json={"count": 3})


def test_risk_hard_cap_blocks(monkeypatch):
    _seed_once()
    aid = client.get("/api/accounts").json()["accounts"][0]["id"]
    cap = client.get(f"/api/accounts/{aid}").json()["capital"]
    # Risk equal to capital (100%) must be refused outright, even with confirm.
    r = client.post(f"/api/accounts/{aid}/risk", json={"mode": "fixed_money", "amount": cap, "confirm": True})
    assert r.status_code == 400
    assert "hard cap" in r.json()["detail"].lower()


def test_panic_stop_all(monkeypatch):
    _seed_once()
    res = client.post("/api/accounts/stop-all")
    assert res.status_code == 200
    assert "stopped" in res.json()


def test_password_never_in_responses(monkeypatch):
    firm = client.get("/api/prop-firms").json()["prop_firms"][0]["id"]
    body = {"prop_firm_id": firm, "platform_key": "mock", "login": "99",
            "password": "TOP-SECRET-xyz", "seed_balance": 10000}
    created = client.post("/api/accounts", json=body).json()
    assert "TOP-SECRET-xyz" not in str(created)
    aid = created["account"]["id"]
    detail = client.get(f"/api/accounts/{aid}").json()
    assert "TOP-SECRET-xyz" not in str(detail)
