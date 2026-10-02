# Platform connectors — status & how to finish each

Trading Hub talks to every platform through one abstraction
(`PlatformConnector` + `PlatformCapabilities`). A connector **only declares what
it can genuinely do** (§9) and never fabricates data (§88). Below is the honest
status and the exact integration path for each.

| Platform | Status | What it needs / how it works |
|---|---|---|
| **Mock** | ✅ Full, verified | Built-in simulation (all capabilities + fault injection). Runs anywhere. |
| **MetaTrader 5** | ✅ Full (on Windows) | `MetaTrader5` package for reads; **TradingHubBridge** EA + Windows agent for instances, heartbeat, RUN/STOP, risk delivery. See below. |
| **Tradovate** | 🟩 Implemented, unverified | REST (futures). `/auth/accesstokenrequest` → `/account/list`, `/cashBalance/...`, `/product/list`, `/position/list`. Creds: user/pass + app_id/cid/sec/device_id; `server` picks live/demo. Reads only. |
| **TradeLocker** | 🟩 Implemented, unverified | REST (CFD). JWT auth → `/trade/accounts/{id}/state\|instruments\|positions`. Creds: email/password + `tl_server`. Reads only. |
| **DXtrade** | 🟩 Implemented, unverified | REST. `/api/auth/login` → `/api/accounts\|instruments\|positions`. Creds: user/pass + `domain` + endpoint. Reads only. |
| **Match-Trader** | 🟩 Implemented, unverified | REST. `/mtr-api/{uuid}/login` → balance/instruments/positions. Creds: email/password + `system_uuid` + endpoint. Reads only. |
| **MetaTrader 4** | 🟧 Bridge shipped | File-bridge model; MQL4 EA provided (`assets/mt4/`). No official MT4 Python API; reads come from the bridge's `account.json`. |
| **cTrader** | 🔌 Driver-gated | Activates when `pip install ctrader-open-api` is present; OAuth app (client_id/secret/access_token) + ctidTraderAccountId. Protobuf/TLS. |
| **NinjaTrader** | 🔌 Driver-gated (Windows) | NinjaTrader 8 ATI socket (127.0.0.1:36973) + OIF file drop. Active only on Windows with NT8 running. |
| **Rithmic** | 🔌 Driver-gated | Licensed R\|API+ SDK/gateway + system name + credentials. Not faked without the SDK. |
| **Quantower** | 🔌 Driver-gated | In-app Quantower bridge plugin on the host (bridge port). |

Legend — ✅ verified · 🟩 **implemented against the documented API but not yet
tested against a live account** (verify with real credentials, then flip to ✅)
· 🟧 partial · 🔌 real code that activates when its SDK / host dependency is
present, honest-empty otherwise. Every connector is listed in the UI with its
exact "Requires: …" note and the credential fields it needs; `capabilities()`
never claims what the code can't do (§88). Adding/finishing one is a
self-contained change under `app/connectors/<key>/` — no core edits (§8).

> The 🟩 REST connectors read account, instruments and positions (broker APIs
> have no Expert-Advisor model, so robot start/stop is intentionally absent —
> your algo connects to the same API). Trading Hub still does discovery, risk
> sizing and monitoring for them.

---

## MetaTrader 5 — the full loop (what runs on your PC)

When you add an MT5 account, the Windows agent (`app/terminal/mt5_agent.py`) and
the connector do this for real:

1. **Locate** your MT5 install (registry + common dirs).
2. **Create a portable instance** per account: a private copy of the terminal
   with its own data folder, launched with `/portable` — so N accounts never mix
   (§14-15).
3. **Install + compile** the companion EA `TradingHubBridge.mq5` into the
   instance (via `metaeditor64.exe /compile`).
4. **Connect** through that instance (`MetaTrader5.initialize(path=…)` + login
   with your **server**).
5. **Deliver risk**: write the robot config to `MQL5/Files/TradingHub/config.json`
   *and* an EA input preset `Presets/StrategyA.set` (RISK_MODE + RISK_AMOUNT).
6. **Start/stop**: write `command.txt` = `RUN`/`STOP`; the bridge EA publishes the
   `TH_ENABLED` global the strategy honours.
7. **Heartbeat + monitoring**: the bridge EA writes `heartbeat.txt` and
   `account.json` every couple of seconds; the engine reads them for liveness,
   balance/equity and open positions (§56, §66). Recovery restarts the terminal
   and waits for the heartbeat to return — it never closes positions (§52).

### One-time setup per strategy
Trading Hub manages risk, heartbeat and start/stop automatically. For your own
strategy EA to act on them, have it read two global variables the bridge keeps
updated (standard MQL5):

```mql5
double riskAmount = GlobalVariableGet("TH_RISK_AMOUNT"); // money risk per trade
bool   enabled    = GlobalVariableGet("TH_ENABLED") > 0; // RUN/STOP from the Hub
// size a trade with the shared helper (same math as the engine):
double lots = THCalculateVolume(_Symbol, riskAmount, stopLossDistance);
```

The `THCalculateVolume` helper ships inside the bridge EA and mirrors the Python
risk engine exactly (§38), so volumes match everywhere.
