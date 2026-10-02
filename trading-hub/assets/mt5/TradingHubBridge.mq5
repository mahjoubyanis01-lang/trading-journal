//+------------------------------------------------------------------+
//|                                          TradingHubBridge.mq5     |
//|  Companion EA that bridges a MetaTrader 5 terminal instance with  |
//|  the local Trading Hub engine (spec §21, §66).                    |
//|                                                                   |
//|  Attach it to ONE chart of a Trading Hub managed instance. It:    |
//|   - writes  Files/TradingHub/heartbeat.txt (GMT unix seconds)     |
//|   - writes  Files/TradingHub/account.json  (balance/equity/pos.)  |
//|   - reads   Files/TradingHub/config.json   (risk + markets)       |
//|   - reads   Files/TradingHub/command.txt   ("RUN"/"STOP")         |
//|   - publishes global variables TH_ENABLED / TH_RISK_AMOUNT /      |
//|     TH_RISK_MODE so the user's strategy EA can honour them.       |
//|                                                                   |
//|  It never opens trades itself - the strategy EA does (spec §2).   |
//+------------------------------------------------------------------+
#property copyright "Trading Hub"
#property version   "1.00"
#property strict

input int HeartbeatSeconds = 2;         // how often to refresh heartbeat/account

string TH_DIR = "TradingHub\\";

//+------------------------------------------------------------------+
int OnInit()
  {
   EventSetTimer(HeartbeatSeconds);
   WriteHeartbeat();
   PublishConfig();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
  }

void OnTimer()
  {
   WriteHeartbeat();
   WriteAccount();
   PublishConfig();
   ApplyCommand();
  }

//+------------------------------------------------------------------+
//| Heartbeat: GMT unix seconds                                       |
//+------------------------------------------------------------------+
void WriteHeartbeat()
  {
   int h = FileOpen(TH_DIR + "heartbeat.txt", FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h == INVALID_HANDLE)
      return;
   FileWriteString(h, IntegerToString((long)TimeGMT()));
   FileClose(h);
  }

//+------------------------------------------------------------------+
//| Account snapshot as JSON                                          |
//+------------------------------------------------------------------+
void WriteAccount()
  {
   int h = FileOpen(TH_DIR + "account.json", FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h == INVALID_HANDLE)
      return;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   string cur = AccountInfoString(ACCOUNT_CURRENCY);
   long   login = AccountInfoInteger(ACCOUNT_LOGIN);

   string json = "{";
   json += "\"login\":" + IntegerToString(login) + ",";
   json += "\"balance\":" + DoubleToString(bal, 2) + ",";
   json += "\"equity\":" + DoubleToString(eq, 2) + ",";
   json += "\"currency\":\"" + cur + "\",";
   json += "\"positions\":[";
   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
     {
      string sym = PositionGetSymbol(i);
      if(sym == "")
         continue;
      double vol = PositionGetDouble(POSITION_VOLUME);
      double profit = PositionGetDouble(POSITION_PROFIT);
      long   ptype = PositionGetInteger(POSITION_TYPE);
      if(i > 0)
         json += ",";
      json += "{\"symbol\":\"" + sym + "\",";
      json += "\"volume\":" + DoubleToString(vol, 2) + ",";
      json += "\"direction\":\"" + (ptype == POSITION_TYPE_BUY ? "buy" : "sell") + "\",";
      json += "\"profit\":" + DoubleToString(profit, 2) + "}";
     }
   json += "]}";
   FileWriteString(h, json);
   FileClose(h);
  }

//+------------------------------------------------------------------+
//| Publish risk config as global variables for the strategy EA       |
//+------------------------------------------------------------------+
void PublishConfig()
  {
   int h = FileOpen(TH_DIR + "config.json", FILE_READ|FILE_TXT|FILE_ANSI);
   if(h == INVALID_HANDLE)
      return;
   string content = "";
   while(!FileIsEnding(h))
      content += FileReadString(h);
   FileClose(h);

   double amount = JsonNumber(content, "risk_amount");
   string mode   = JsonString(content, "risk_mode");
   bool   enabled = (JsonString(content, "enabled") == "true") || (JsonNumber(content, "enabled") == 1);

   GlobalVariableSet("TH_RISK_AMOUNT", amount);
   GlobalVariableSet("TH_RISK_MODE", mode == "dynamic_percent" ? 1 : 0);
   GlobalVariableSet("TH_ENABLED", enabled ? 1 : 0);
  }

//+------------------------------------------------------------------+
//| Honour RUN/STOP from the engine via the TH_ENABLED flag           |
//+------------------------------------------------------------------+
void ApplyCommand()
  {
   int h = FileOpen(TH_DIR + "command.txt", FILE_READ|FILE_TXT|FILE_ANSI);
   if(h == INVALID_HANDLE)
      return;
   string cmd = FileReadString(h);
   FileClose(h);
   if(StringLen(cmd) == 0)
      return;
   GlobalVariableSet("TH_ENABLED", (StringCompare(cmd, "RUN", false) == 0) ? 1 : 0);
  }

//+------------------------------------------------------------------+
//| Money-risk -> normalised volume. Strategy EAs may call this.      |
//| (Mirror of the Python risk engine, spec §38.)                     |
//+------------------------------------------------------------------+
double THCalculateVolume(string symbol, double riskMoney, double slDistance)
  {
   if(riskMoney <= 0 || slDistance <= 0)
      return(0.0);
   double tickSize  = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double stepVol   = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double minVol    = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxVol    = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   if(tickSize <= 0 || tickValue <= 0)
      return(0.0);                                   // UNKNOWN specs -> refuse (§88)
   double lossPerLot = (slDistance / tickSize) * tickValue;
   if(lossPerLot <= 0)
      return(0.0);
   double vol = riskMoney / lossPerLot;
   vol = MathFloor(vol / stepVol) * stepVol;         // never exceed requested risk
   if(vol < minVol) vol = minVol;
   if(maxVol > 0 && vol > maxVol) vol = maxVol;
   return(NormalizeDouble(vol, 2));
  }

//+------------------------------------------------------------------+
//| Minimal JSON helpers (flat objects only)                          |
//+------------------------------------------------------------------+
double JsonNumber(string src, string key)
  {
   int p = StringFind(src, "\"" + key + "\"");
   if(p < 0) return(0.0);
   p = StringFind(src, ":", p);
   if(p < 0) return(0.0);
   int e = p + 1;
   while(e < StringLen(src))
     {
      ushort c = StringGetCharacter(src, e);
      if(c == ',' || c == '}' || c == ']') break;
      e++;
     }
   string val = StringSubstr(src, p + 1, e - p - 1);
   StringTrimLeft(val); StringTrimRight(val);
   return(StringToDouble(val));
  }

string JsonString(string src, string key)
  {
   int p = StringFind(src, "\"" + key + "\"");
   if(p < 0) return("");
   p = StringFind(src, ":", p);
   if(p < 0) return("");
   int q1 = StringFind(src, "\"", p);
   if(q1 < 0) return("");
   int q2 = StringFind(src, "\"", q1 + 1);
   if(q2 < 0) return("");
   return(StringSubstr(src, q1 + 1, q2 - q1 - 1));
  }
//+------------------------------------------------------------------+
