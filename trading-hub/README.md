# Trading Hub

A **local** control center for running one algorithmic trading strategy across
many independent prop-firm / broker accounts, platforms, terminals and robots —
from 1 account to 100+ — with as little manual work as possible.

> Principle: **DÉTECTER → CONFIGURER → EXÉCUTER → VÉRIFIER → SURVEILLER → RÉCUPÉRER**.
> The user makes the decisions; Trading Hub handles the technical complexity.
> *Everything automatic, exceptions visible.*

This repository contains a working **MVP**: the full local engine (backend) with
a mock platform so the whole workflow runs on any OS, a test suite covering the
acceptance criteria, and a React/TypeScript cockpit UI.

---

## What this is NOT

- **Not a trade copier.** There is no master/slave, no mirror, no position
  replication or synchronisation. Each account is fully independent; 50 accounts
  on the same strategy run 50 independent robot instances that place their own
  orders. (spec §2)
- **Not VPS-centric.** It runs on the user's Windows PC and works with no remote
  server. (spec §3)

---

## Quick start

### Backend (engine + API)
```bash
cd backend
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
- API docs: http://localhost:8000/docs
- Health:   http://localhost:8000/health
- Seed demo data (50 simulated accounts):
  `curl -X POST localhost:8000/seed-demo -H 'content-type: application/json' -d '{"count":50}'`

### Frontend (cockpit UI)
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api and /ws to :8000
```

### Tests
```bash
cd backend && . .venv/bin/activate
python -m pytest -q      # 50 tests: engines (unit) + full workflow (integration)
```

---

## Mock mode (default)

`TH_MOCK_MODE=true` (the default) makes a simulated platform available under the
`mock` key. It implements every capability and can inject faults (crash the
robot/terminal, drop the heartbeat) so you can see auto-recovery work — on Linux,
macOS or Windows, with no real broker. This is how the test suite and the demo
data exercise the exact same code path as production. (spec §70-71)

---

## What is real vs. what needs the Windows agent

Financial software must never fake an integration (spec §88). Honest status of
this MVP:

| Area | Status |
|---|---|
| Core engine: accounts, risk, market mapping + confidence, drawdown, performance, recovery state machine, heartbeat, events, alerts, health | **Real & unit-tested.** Pure, platform-independent logic. |
| Mock platform (discovery, account reads, robot lifecycle, fault injection) | **Real**, fully simulated. |
| REST API + WebSocket live events + SQLite persistence | **Real.** |
| Credential storage via OS keyring / Windows Credential Manager (DPAPI) | **Real**, with a safe process-memory fallback when no keyring exists. Passwords are never stored in the DB, logs, JSON or API responses (spec §7). |
| **MT5 reads** (connect, balance/equity, instrument specs, positions) | **Implemented** via the official `MetaTrader5` Python package — runs only on **Windows with that package installed**. On other machines the connector honestly reports *no* capabilities and the account shows as "platform unavailable". |
| **MT5 terminal/robot lifecycle** (portable instances, EA install, templates, process supervision, heartbeat file) | **Designed & abstracted**, to be completed in the Windows agent. The MT5 Python API cannot do these — they are file-system + process operations. See `app/connectors/mt5/mt5.py` and `app/terminal/manager.py` for the exact plan. |
| Other connectors (cTrader, Tradovate, NinjaTrader, …) | **Not yet built.** The connector abstraction + registry make each a self-contained addition with no core changes (spec §8). |
| Windows auto-start / background agent | **Designed** (spec §65); not packaged in this MVP. |

---

## Acceptance criteria (spec §86)

All ten are covered by the test suite (`backend/tests/`):

1. Add an MT5-style account → connected, terminal created, robot configured, template applied.
2. 10 000 $ @ 0.5% → **Risk Money = 50 $** (fixed money, not a bare %).
3. Change 50 $ → 75 $ → robot reconfigured to 75 $/position.
4. Unrecognised market → search on platform → pick symbol → add to robot → mapping remembered.
5. Robot dies → heartbeat lost → auto-recovery → robot restarted → heartbeat restored.
6. Terminal closes → terminal restart → reconnect → robot restart.
7. 50 simulated accounts → dashboard stays usable.
8. Account page shows balance/equity/P&L/perf/drawdown/risk/robot/terminal/markets.
9. Prop-firm page shows account count, capital, P&L, performance, robots active.
10. Global dashboard shows capital, P&L today/month, performance, drawdown, counts, alerts.

See `ARCHITECTURE.md` for the component map, data flow and extension points, and
`backend/app/connectors/mt5/mt5.py` for the precise, honest MT5 scope.
