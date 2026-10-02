//+------------------------------------------------------------------+
//|                                          TradingHubBridge.mq4     |
//|  MT4 companion EA - same role as the MT5 bridge (spec §21, §66).  |
//|  Writes heartbeat.txt + account.json, reads config.json/command,  |
//|  publishes TH_ENABLED / TH_RISK_AMOUNT / TH_RISK_MODE globals.     |
//|  Never trades (spec §2).                                          |
//+------------------------------------------------------------------+
#property copyright "Trading Hub"
#property version   "1.00"
#property strict

input int HeartbeatSeconds = 2;

string TH_DIR = "TradingHub\\";

int OnInit()
  {
   EventSetTimer(HeartbeatSeconds);
   WriteHeartbeat();
   PublishConfig();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason) { EventKillTimer(); }

void OnTimer()
  {
   WriteHeartbeat();
   WriteAccount();
   PublishConfig();
   ApplyCommand();
  }

void WriteHeartbeat()
  {
   int h = FileOpen(TH_DIR + "heartbeat.txt", FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   FileWriteString(h, IntegerToString((int)TimeGMT()));
   FileClose(h);
  }

void WriteAccount()
  {
   int h = FileOpen(TH_DIR + "account.json", FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   string json = "{";
   json += "\"login\":" + IntegerToString(AccountNumber()) + ",";
   json += "\"balance\":" + DoubleToString(AccountBalance(), 2) + ",";
   json += "\"equity\":" + DoubleToString(AccountEquity(), 2) + ",";
   json += "\"currency\":\"" + AccountCurrency() + "\",";
   json += "\"positions\":[";
   int count = 0;
   for(int i = 0; i < OrdersTotal(); i++)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderType() > OP_SELL) continue;  // skip pending
      if(count > 0) json += ",";
      json += "{\"symbol\":\"" + OrderSymbol() + "\",";
      json += "\"volume\":" + DoubleToString(OrderLots(), 2) + ",";
      json += "\"direction\":\"" + (OrderType() == OP_BUY ? "buy" : "sell") + "\",";
      json += "\"profit\":" + DoubleToString(OrderProfit(), 2) + "}";
      count++;
     }
   json += "]}";
   FileWriteString(h, json);
   FileClose(h);
  }

void PublishConfig()
  {
   int h = FileOpen(TH_DIR + "config.json", FILE_READ|FILE_TXT|FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   string content = "";
   while(!FileIsEnding(h)) content += FileReadString(h);
   FileClose(h);
   GlobalVariableSet("TH_RISK_AMOUNT", JsonNumber(content, "risk_amount"));
   GlobalVariableSet("TH_RISK_MODE", JsonString(content, "risk_mode") == "dynamic_percent" ? 1 : 0);
   GlobalVariableSet("TH_ENABLED", JsonString(content, "enabled") == "true" ? 1 : 0);
  }

void ApplyCommand()
  {
   int h = FileOpen(TH_DIR + "command.txt", FILE_READ|FILE_TXT|FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   string cmd = FileReadString(h);
   FileClose(h);
   if(StringLen(cmd) == 0) return;
   GlobalVariableSet("TH_ENABLED", StringCompare(cmd, "RUN", false) == 0 ? 1 : 0);
  }

double THCalculateVolume(string symbol, double riskMoney, double slDistance)
  {
   if(riskMoney <= 0 || slDistance <= 0) return(0.0);
   double tickSize  = MarketInfo(symbol, MODE_TICKSIZE);
   double tickValue = MarketInfo(symbol, MODE_TICKVALUE);
   double stepVol   = MarketInfo(symbol, MODE_LOTSTEP);
   double minVol    = MarketInfo(symbol, MODE_MINLOT);
   double maxVol    = MarketInfo(symbol, MODE_MAXLOT);
   if(tickSize <= 0 || tickValue <= 0) return(0.0);
   double lossPerLot = (slDistance / tickSize) * tickValue;
   if(lossPerLot <= 0) return(0.0);
   double vol = riskMoney / lossPerLot;
   vol = MathFloor(vol / stepVol) * stepVol;
   if(vol < minVol) vol = minVol;
   if(maxVol > 0 && vol > maxVol) vol = maxVol;
   return(NormalizeDouble(vol, 2));
  }

double JsonNumber(string src, string key)
  {
   int p = StringFind(src, "\"" + key + "\"");
   if(p < 0) return(0.0);
   p = StringFind(src, ":", p);
   if(p < 0) return(0.0);
   int e = p + 1;
   while(e < StringLen(src))
     {
      int c = StringGetChar(src, e);
      if(c == ',' || c == '}' || c == ']') break;
      e++;
     }
   string val = StringSubstr(src, p + 1, e - p - 1);
   StringTrimLeft(val); StringTrimRight(val);
   return(StrToDouble(val));
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
