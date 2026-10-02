"""End-to-end API tests covering the acceptance criteria (§86, Tests 1-10)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # runs lifespan: init_db + seed_reference
        yield c


def _fundednext_id(client) -> int:
    firms = client.get("/api/prop-firms").json()["prop_firms"]
    return next(f["id"] for f in firms if f["name"] == "FundedNext")


def _tenk_id(client) -> int:
    """The 10 000 $ mock account created by the workflow test (robust to other
    accounts existing in the shared test DB)."""
    accounts = client.get("/api/accounts").json()["accounts"]
    for a in accounts:
        if a["name"] == "FundedNext 10K":
            return a["id"]
    return accounts[0]["id"]


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_platform_capabilities_are_honest(client):
    platforms = {p["key"]: p for p in client.get("/api/platforms").json()["platforms"]}
    # mock supports everything and is available here
    assert platforms["mock"]["capabilities"]["can_start_robot"] is True
    assert platforms["mock"]["available"] is True
    # mt5 is registered but NOT available on this (Linux) machine, and says why (§88)
    assert platforms["mt5"]["available"] is False
    assert platforms["mt5"]["capabilities"].get("can_connect") in (False, None)
    assert "MetaTrader 5" in platforms["mt5"]["requirement"]
    # additional platforms are listed honestly with a requirement note
    assert platforms["tradovate"]["available"] is False
    assert platforms["tradovate"]["requirement"]


def test_add_mt5_like_account_workflow(client):
    # Acceptance Tests 1, 2 : add account, 10 000 $ @ 0.5% => risk 50 $
    body = {
        "prop_firm_id": _fundednext_id(client), "platform_key": "mock",
        "login": "1001001", "password": "secret-pw", "seed_balance": 10_000,
    }
    r = client.post("/api/accounts", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    acc = data["account"]
    assert acc["name"] == "FundedNext 10K"           # auto-named (§11)
    assert acc["risk_amount"] == 50.0                 # §32
    assert acc["risk_mode"] == "fixed_money"
    assert acc["health"] == "operational"
    assert acc["robot_status"] == "active"
    assert acc["terminal"].startswith("MOCK-")
    # password never echoed back anywhere
    assert "password" not in str(data).lower() or "secret-pw" not in str(data)
    assert "secret-pw" not in str(data)
    # workflow produced the step sequence (§12)
    names = [s["name"] for s in data["steps"]]
    assert "Connect" in names and "Risk" in names and "Start robot" in names


def test_change_risk_50_to_75(client):
    # Acceptance Test 3
    aid = _tenk_id(client)
    r = client.post(f"/api/accounts/{aid}/risk", json={"mode": "fixed_money", "amount": 75})
    assert r.status_code == 200, r.text
    assert r.json()["risk_amount"] == 75.0


def test_risk_guard_requires_confirmation(client):
    # §39 : huge risk => needs confirmation before applying
    aid = _tenk_id(client)
    r = client.post(f"/api/accounts/{aid}/risk", json={"mode": "fixed_money", "amount": 5000})
    assert r.json().get("needs_confirmation") is True
    # confirm applies it
    r2 = client.post(f"/api/accounts/{aid}/risk", json={"mode": "fixed_money", "amount": 5000, "confirm": True})
    assert r2.status_code == 200
    # put it back to a sane value
    client.post(f"/api/accounts/{aid}/risk", json={"mode": "fixed_money", "amount": 50})


def test_market_search_and_map(client):
    # Acceptance Test 4 : search on platform + add to robot
    aid = _tenk_id(client)
    r = client.post(f"/api/accounts/{aid}/markets/search", json={"universal_symbol": "NASDAQ100"})
    cands = r.json()["candidates"]
    assert any(c["real_symbol"] == "USTEC" for c in cands)
    r2 = client.post(f"/api/accounts/{aid}/markets/map",
                     json={"universal_symbol": "NASDAQ100", "real_symbol": "USTEC"})
    assert r2.status_code == 200
    markets = {m["universal"]: m for m in r2.json()["markets"]}
    assert markets["NASDAQ100"]["real"] == "USTEC"
    assert markets["NASDAQ100"]["verified"] is True


def test_recovery_from_robot_crash(client):
    # Acceptance Test 5
    aid = _tenk_id(client)
    client.post(f"/api/sim/{aid}/fault", json={"fault": "robot"})
    out = client.post(f"/api/accounts/{aid}/recover").json()
    assert out["outcome"] == "recovered"


def test_recovery_from_terminal_crash(client):
    # Acceptance Test 6
    aid = _tenk_id(client)
    client.post(f"/api/sim/{aid}/fault", json={"fault": "terminal"})
    out = client.post(f"/api/accounts/{aid}/recover").json()
    assert out["outcome"] == "recovered"


def test_seed_50_accounts_and_dashboard(client):
    # Acceptance Tests 7, 9, 10 : 50 accounts, dashboard + prop firm aggregates
    created = client.post("/api/seed-demo", json={"count": 50}).json()["created"]
    assert created >= 1
    dash = client.get("/api/dashboard").json()
    assert dash["accounts"] >= 50
    assert dash["capital"] > 0
    assert "robots_active" in dash and dash["robots_total"] >= 50
    assert isinstance(dash["prop_firms"], list) and dash["prop_firms"]
    # prop firm page (Test 9)
    pf_id = dash["prop_firms"][0]["id"] if "id" in dash["prop_firms"][0] else _fundednext_id(client)
    pf = client.get(f"/api/prop-firms/{pf_id}").json()
    assert pf["accounts"] >= 1 and "capital" in pf


def test_account_detail(client):
    # Acceptance Test 8
    aid = _tenk_id(client)
    d = client.get(f"/api/accounts/{aid}").json()
    for key in ("balance", "equity", "pnl_today", "pnl_month", "performance_pct",
                "risk_amount", "robot_status", "terminal", "markets"):
        assert key in d
