# Platform connectors — status & how to finish each

Trading Hub talks to every platform through one abstraction
(`PlatformConnector` + `PlatformCapabilities`). A connector **only declares what
it can genuinely do** (§9) and never fabricates data (§88). Below is the honest
status and the exact integration path for each.

| Platform | Status | What it needs / how it works |
|---|---|---|
| **Mock** | ✅ Full | Built-in simulation (all capabilities + fault injection). Runs anywhere. |
| **MetaTrader 5** | ✅ Full (on Windows) | `MetaTrader5` Python package for reads; the **TradingHubBridge** EA + the Windows agent for instances, heartbeat, RUN/STOP, risk delivery. See below. |
| **MetaTrader 4** | 🟧 Bridge shipped | Same file-bridge model; MQL4 EA provided (`assets/mt4/`). No official MT4 Python API, so reads come from the bridge's `account.json`. Wiring the MT4 agent mirrors MT5. |
| cTrader | ⬜ Scaffold | cTrader Open API (OAuth app id/secret, protobuf over TCP). Reads account/symbols/positions; bots are cBots managed in-platform. |
| Tradovate | ⬜ Scaffold | REST + WebSocket (user/pass/app id/secret/device). Futures account/positions/instruments. |
| NinjaTrader | ⬜ Scaffold | NinjaTrader 8 ATI / socket API on Windows; strategies are NinjaScript. |
| Rithmic | ⬜ Scaffold | R\|API+ credentials + gateway (futures). |
| DXtrade | ⬜ Scaffold | Broker REST/WebSocket credentials + endpoint. |
| Match-Trader | ⬜ Scaffold | Broker API credentials + endpoint. |
| TradeLocker | ⬜ Scaffold | REST API (email/password/server). |
| Quantower | ⬜ Scaffold | Quantower API / plugin bridge on the host. |

⬜ Scaffold = registered and listed in the UI with a precise "Requires: …" note,
`capabilities()` all false until implemented. Adding one is a self-contained
file under `app/connectors/<key>/` + one `register()` line — no core changes (§8).

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
