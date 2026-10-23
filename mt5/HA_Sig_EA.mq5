//+------------------------------------------------------------------+
//|                                                    HA_Sig_EA.mq5 |
//|  Expert Advisor MetaTrader 5 -- portage de la strategie HA Sig   |
//|                                                                  |
//|  Logique (identique au script Pine "HA Sig Strategy") :          |
//|   - Bougies Heiken Ashi calculees sur les bougies reelles        |
//|   - Momentum Squeeze (LazyBear) : val = regression lineaire de   |
//|     close - moy(moy(hh(20), ll(20)), sma(close,20)) sur 20 b.    |
//|   - Normalisation -100/+100 sur l'amplitude recente (100 b.)     |
//|   - Bougie VIVE = |normVal| >= seuil ET momentum en renforcement |
//|   - Cycle violet/rouge ; reference = bougie vive ET P1           |
//|     (extension de structure), au plus haut / plus bas du cycle   |
//|   - Signal = cassure du bas (violet) / haut (rouge) de la        |
//|     reference, a la cloture HA ; cycle perdu apres N bougies     |
//|     non vives consecutives                                       |
//|   - SL = plus bas / plus haut des N dernieres bougies (-1 R)     |
//|   - Break-even a +1 R ; sortie a la croix de perte de momentum   |
//|     (2 bougies de repli consecutives) UNIQUEMENT en PnL positif  |
//|   - Un seul trade a la fois ; taille par risque en argent        |
//|                                                                  |
//|  Differences avec TradingView :                                  |
//|   - tout est evalue a la cloture de bougie ; l'ordre au marche   |
//|     est execute au tout debut de la bougie suivante (vs cloture  |
//|     de la bougie du signal sur TradingView)                      |
//|   - l'heure de reset de la structure est en HEURE SERVEUR du     |
//|     broker (ajuster InpResetHour pour correspondre a Paris)      |
//+------------------------------------------------------------------+
#property copyright "mahjo"
#property version   "1.00"
#property strict

// Aucune dependance : les ordres passent par OrderSend() natif,
// pas besoin de la bibliotheque standard <Trade\Trade.mqh>.

//=================== INPUTS =========================================
input group "Squeeze momentum"
input int    InpKcLength   = 20;     // Longueur KC (calcul du momentum)
input int    InpNormLen    = 100;    // Fenetre de normalisation

input group "Signaux : cassure de la bougie extreme"
input int    InpVividZone  = 75;     // Seuil de couleur vive (0-100)
input bool   InpBreakOnClose = true; // Cassure a la cloture (sinon meche)
input int    InpCrossBars  = 2;      // Bougies de repli pour la croix
input int    InpMaxWait    = 0;      // Validite du niveau (barres, 0 = illimitee)
input int    InpCancelBars = 3;      // Bougies non vives consecutives = cycle perdu

input group "Market structure (P1)"
input bool   InpUseP1      = true;   // Reference = bougie P1 obligatoire
input int    InpResetHour  = 0;      // Reset structure : heure (serveur)
input int    InpResetMin   = 0;      // Reset structure : minute

input group "Risque / gestion"
input double InpRiskMoney  = 1000.0; // Risque par trade (devise du compte, 0 = volume min)
input int    InpSlLen      = 5;      // Bougies pour le SL
input bool   InpUseBE      = true;   // Break-even a +N R
input double InpBeTrigger  = 1.0;    // Declenchement du break-even (en R)
input long   InpMagic      = 20251023; // Magic number

input group "Affichage (historique sur le graphique)"
input bool   InpDraw        = true;  // Dessiner l'historique des trades
input bool   InpClearOnInit = false; // Effacer l'historique au (re)demarrage

//=================== ETAT GLOBAL ====================================
// Heiken Ashi (etat de la derniere bougie close traitee)
bool   g_haInit = false;
double g_haOpen = 0, g_haClose = 0, g_haHigh = 0, g_haLow = 0;
double g_haOpenPrev = 0, g_haClosePrev = 0;

// Momentum
double g_valHist[];        // historique de val (0 = plus recent)
double g_val = 0, g_valPrev = 0;
double g_normVal = 0;
bool   g_strengthening = false;
int    g_momDnCnt = 0, g_momUpCnt = 0;

// Market structure (moteur P1-P4 reduit)
bool   g_msInit = false;
int    g_msTr = 1, g_msSt = 0;
double g_msP1e = 0, g_msP1o = 0, g_msP2e = 0, g_msPp2 = 0, g_msPp1 = 0;
bool   g_msP2eSet = false, g_msPp2Set = false, g_msPp1Set = false, g_msHp1 = false;

// Cycle de couleur vive
int    g_epDir = 0;              // 1 = violet, -1 = rouge, 0 = aucun
double g_refHi = 0, g_refLo = 0;
bool   g_refSet = false;
long   g_refBar = -1;
int    g_fadeCnt = 0;

// Croix de perte de momentum
int    g_pendingExit = 0;        // 1 apres achat, -1 apres vente
long   g_sigBar = -1;
double g_sigPrice = 0;

// Trade en cours (notre suivi logique ; le stop reel est chez le broker)
bool   g_trOpen = false;
int    g_trDir = 0;
double g_trEnt = 0, g_trSl = 0, g_trRisk = 0;
bool   g_trBE = false;
long   g_trStartBar = -1;

// Compteur de bougies closes traitees
long   g_barCount = 0;
datetime g_lastBarTime = 0;

// Statistiques en R
int    g_btN = 0, g_btWin = 0, g_btLoss = 0, g_btBE = 0;
double g_btSum = 0, g_btGrossW = 0, g_btGrossL = 0, g_btPeak = 0, g_btDdMax = 0;

//=================== OUTILS SERIES ==================================
double HighestHigh(int start, int count)
  {
   int idx = iHighest(_Symbol, _Period, MODE_HIGH, count, start);
   return idx >= 0 ? iHigh(_Symbol, _Period, idx) : iHigh(_Symbol, _Period, start);
  }

double LowestLow(int start, int count)
  {
   int idx = iLowest(_Symbol, _Period, MODE_LOW, count, start);
   return idx >= 0 ? iLow(_Symbol, _Period, idx) : iLow(_Symbol, _Period, start);
  }

double SmaClose(int start, int count)
  {
   double s = 0;
   for(int i = 0; i < count; i++)
      s += iClose(_Symbol, _Period, start + i);
   return s / count;
  }

// Equivalent de ta.linreg(source, len, 0) de Pine sur la bougie 'shift'
double ComputeVal(int shift)
  {
   int len = InpKcLength;
   double sx = 0, sy = 0, sxy = 0, sxx = 0;
   for(int k = 0; k < len; k++)
     {
      double hh   = HighestHigh(shift + k, len);
      double ll   = LowestLow(shift + k, len);
      double smac = SmaClose(shift + k, len);
      double y = iClose(_Symbol, _Period, shift + k) - (((hh + ll) / 2.0) + smac) / 2.0;
      double x = (double)(len - 1 - k);    // 0 = plus ancien, len-1 = plus recent
      sx += x; sy += y; sxy += x * y; sxx += x * x;
     }
   double n = (double)len;
   double denom = n * sxx - sx * sx;
   double b = denom != 0 ? (n * sxy - sx * sy) / denom : 0;
   double a = (sy - b * sx) / n;
   return a + b * (len - 1);
  }

//=================== ORDRES (OrderSend natif) =======================
ENUM_ORDER_TYPE_FILLING FillingMode()
  {
   long fl = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((fl & SYMBOL_FILLING_FOK) != 0) return ORDER_FILLING_FOK;
   if((fl & SYMBOL_FILLING_IOC) != 0) return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
  }

bool OpenMarket(int dir, double lots, double sl)
  {
   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);
   req.action       = TRADE_ACTION_DEAL;
   req.symbol       = _Symbol;
   req.volume       = lots;
   req.type         = dir == 1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   req.price        = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   req.sl           = NormalizeDouble(sl, _Digits);
   req.deviation    = 20;
   req.magic        = (ulong)InpMagic;
   req.comment      = dir == 1 ? "HA Sig L" : "HA Sig S";
   req.type_filling = FillingMode();
   if(!OrderSend(req, res) || (res.retcode != TRADE_RETCODE_DONE && res.retcode != TRADE_RETCODE_PLACED && res.retcode != TRADE_RETCODE_DONE_PARTIAL))
     {
      PrintFormat("HA Sig EA : echec d'ouverture (retcode %d)", res.retcode);
      return false;
     }
   return true;
  }

bool ModifySL(ulong ticket, double newSl)
  {
   if(!PositionSelectByTicket(ticket)) return false;
   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);
   req.action   = TRADE_ACTION_SLTP;
   req.symbol   = PositionGetString(POSITION_SYMBOL);
   req.position = ticket;
   req.sl       = NormalizeDouble(newSl, _Digits);
   req.tp       = PositionGetDouble(POSITION_TP);
   if(!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE)
     {
      PrintFormat("HA Sig EA : echec de modification du SL (retcode %d)", res.retcode);
      return false;
     }
   return true;
  }

bool CloseByTicket(ulong ticket)
  {
   if(!PositionSelectByTicket(ticket)) return false;
   long   ptype = PositionGetInteger(POSITION_TYPE);
   double vol   = PositionGetDouble(POSITION_VOLUME);
   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);
   req.action       = TRADE_ACTION_DEAL;
   req.symbol       = _Symbol;
   req.position     = ticket;
   req.volume       = vol;
   req.type         = ptype == POSITION_TYPE_BUY ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   req.price        = ptype == POSITION_TYPE_BUY ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   req.deviation    = 20;
   req.magic        = (ulong)InpMagic;
   req.comment      = "HA Sig exit croix";
   req.type_filling = FillingMode();
   if(!OrderSend(req, res) || (res.retcode != TRADE_RETCODE_DONE && res.retcode != TRADE_RETCODE_DONE_PARTIAL))
     {
      PrintFormat("HA Sig EA : echec de cloture (retcode %d)", res.retcode);
      return false;
     }
   return true;
  }

//=================== POSITION =======================================
bool GetOurPosition(ulong &ticket, long &ptype, double &popen)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
        {
         ticket = tk;
         ptype  = PositionGetInteger(POSITION_TYPE);
         popen  = PositionGetDouble(POSITION_PRICE_OPEN);
         return true;
        }
     }
   return false;
  }

double NormalizeLots(double lots)
  {
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step > 0)
      lots = MathFloor(lots / step) * step;
   return MathMin(MathMax(lots, minL), maxL);
  }

double LotsForRisk(double slDistance)
  {
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(InpRiskMoney <= 0 || slDistance <= 0) return minL;
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0 || tickValue <= 0) return minL;
   double riskPerLot = slDistance / tickSize * tickValue;
   if(riskPerLot <= 0) return minL;
   return NormalizeLots(InpRiskMoney / riskPerLot);
  }

//=================== DESSIN DE L'HISTORIQUE =========================
long g_trId = 0;   // identifiant du trade courant (prefixe des objets)

string ObjName(string tag) { return StringFormat("HASIG_%s_%I64d", tag, g_trId); }

void DrawOpen(datetime t, double ent, double sl, int dir)
  {
   if(!InpDraw) return;
   string rn = ObjName("BOX");
   ObjectCreate(0, rn, OBJ_RECTANGLE, 0, t, ent, t, sl);
   ObjectSetInteger(0, rn, OBJPROP_COLOR, C'120,30,30');
   ObjectSetInteger(0, rn, OBJPROP_FILL, true);
   ObjectSetInteger(0, rn, OBJPROP_BACK, true);
   ObjectSetInteger(0, rn, OBJPROP_SELECTABLE, false);
   string en = ObjName("ENT");
   ObjectCreate(0, en, OBJ_TREND, 0, t, ent, t, ent);
   ObjectSetInteger(0, en, OBJPROP_COLOR, clrSilver);
   ObjectSetInteger(0, en, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, en, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, en, OBJPROP_SELECTABLE, false);
   string an = ObjName("IN");
   ObjectCreate(0, an, dir == 1 ? OBJ_ARROW_BUY : OBJ_ARROW_SELL, 0, t, ent);
   ObjectSetInteger(0, an, OBJPROP_COLOR, dir == 1 ? clrLime : clrRed);
   ObjectSetInteger(0, an, OBJPROP_SELECTABLE, false);
  }

void DrawExtend(datetime t)
  {
   if(!InpDraw) return;
   ObjectSetInteger(0, ObjName("BOX"), OBJPROP_TIME, 1, t);
   ObjectSetInteger(0, ObjName("ENT"), OBJPROP_TIME, 1, t);
   if(ObjectFind(0, ObjName("BE")) >= 0)
      ObjectSetInteger(0, ObjName("BE"), OBJPROP_TIME, 1, t);
  }

void DrawBE(datetime t, double ent)
  {
   if(!InpDraw) return;
   string bn = ObjName("BE");
   ObjectCreate(0, bn, OBJ_TREND, 0, t, ent, t, ent);
   ObjectSetInteger(0, bn, OBJPROP_COLOR, clrOrange);
   ObjectSetInteger(0, bn, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetInteger(0, bn, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, bn, OBJPROP_SELECTABLE, false);
   string bt = ObjName("BETXT");
   ObjectCreate(0, bt, OBJ_TEXT, 0, t, ent);
   ObjectSetString(0, bt, OBJPROP_TEXT, "BE");
   ObjectSetInteger(0, bt, OBJPROP_COLOR, clrOrange);
   ObjectSetInteger(0, bt, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, bt, OBJPROP_SELECTABLE, false);
  }

void DrawClose(datetime t, double price, string txt, color col, bool isCross)
  {
   if(!InpDraw) return;
   DrawExtend(t);
   string tn = ObjName("RES");
   ObjectCreate(0, tn, OBJ_TEXT, 0, t, price);
   ObjectSetString(0, tn, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, tn, OBJPROP_COLOR, col);
   ObjectSetInteger(0, tn, OBJPROP_FONTSIZE, 9);
   ObjectSetInteger(0, tn, OBJPROP_SELECTABLE, false);
   if(isCross)
     {
      string xn = ObjName("X");
      ObjectCreate(0, xn, OBJ_ARROW, 0, t, price);
      ObjectSetInteger(0, xn, OBJPROP_ARROWCODE, 251);   // croix (Wingdings)
      ObjectSetInteger(0, xn, OBJPROP_COLOR, clrWhite);
      ObjectSetInteger(0, xn, OBJPROP_SELECTABLE, false);
     }
   ChartRedraw(0);
  }

//=================== STATISTIQUES ===================================
void RecordResult(double res)
  {
   g_btN++;
   g_btSum += res;
   if(res > 0.01)      { g_btWin++;  g_btGrossW += res; }
   else if(res < -0.01){ g_btLoss++; g_btGrossL += -res; }
   else                 g_btBE++;
   g_btPeak  = MathMax(g_btPeak, g_btSum);
   g_btDdMax = MathMax(g_btDdMax, g_btPeak - g_btSum);
   PrintFormat("HA Sig EA : trade clos, resultat %.2f R | PNL total %.2f R", res, g_btSum);
  }

void UpdateComment()
  {
   double ddCur = g_btPeak - g_btSum;
   string pf = g_btGrossL > 0 ? DoubleToString(g_btGrossW / g_btGrossL, 2) : (g_btGrossW > 0 ? "inf" : "-");
   string esp = g_btN > 0 ? DoubleToString(g_btSum / g_btN, 2) + " R" : "-";
   string wr  = g_btN > 0 ? DoubleToString(100.0 * g_btWin / g_btN, 1) + " %" : "-";
   Comment(StringFormat(
      "HA SIG EA - BACKTEST (R)\nTrades: %d (G %d / P %d / BE %d)\nTaux de reussite: %s\nProfit factor: %s\nEsperance/trade: %s\nPNL total: %.2f R\nDrawdown actuel: -%.2f R\nDrawdown max: -%.2f R\nEtat: %s",
      g_btN, g_btWin, g_btLoss, g_btBE, wr, pf, esp, g_btSum, ddCur, g_btDdMax,
      g_trOpen ? (g_trDir == 1 ? "LONG en cours" : "SHORT en cours") : "flat"));
  }

//=================== INIT ===========================================
int OnInit()
  {
   if(InpClearOnInit)
      ObjectsDeleteAll(0, "HASIG_");
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) { Comment(""); }

//=================== COEUR : TRAITEMENT D'UNE BOUGIE CLOSE ==========
void ProcessClosedBar()
  {
   int sh = 1; // la derniere bougie close
   double o = iOpen(_Symbol, _Period, sh);
   double h = iHigh(_Symbol, _Period, sh);
   double l = iLow(_Symbol, _Period, sh);
   double c = iClose(_Symbol, _Period, sh);
   g_barCount++;

   //--- 1) Heiken Ashi
   double haC = (o + h + l + c) / 4.0;
   double haO = g_haInit ? (g_haOpenPrev + g_haClosePrev) / 2.0 : (o + c) / 2.0;
   double haH = MathMax(h, MathMax(haO, haC));
   double haL = MathMin(l, MathMin(haO, haC));
   g_haOpenPrev = haO; g_haClosePrev = haC;
   g_haOpen = haO; g_haClose = haC; g_haHigh = haH; g_haLow = haL;
   g_haInit = true;

   //--- 2) momentum val, normalisation, renforcement, compteurs
   g_valPrev = g_val;
   g_val = ComputeVal(sh);
   int n = ArraySize(g_valHist);
   ArrayResize(g_valHist, n + 1);
   for(int i = n; i > 0; i--) g_valHist[i] = g_valHist[i - 1];
   g_valHist[0] = g_val;
   int span = MathMin(ArraySize(g_valHist), InpNormLen);
   double mx = 1e-10;
   for(int i = 0; i < span; i++) mx = MathMax(mx, MathAbs(g_valHist[i]));
   g_normVal = 100.0 * g_val / mx;
   g_normVal = MathMax(MathMin(g_normVal, 100.0), -100.0);
   g_strengthening = g_val > 0 ? (g_val > g_valPrev) : (g_val < g_valPrev);
   g_momDnCnt = g_val < g_valPrev ? g_momDnCnt + 1 : 0;
   g_momUpCnt = g_val > g_valPrev ? g_momUpCnt + 1 : 0;

   //--- 3) market structure (P1)
   MqlDateTime dtCur, dtPrev;
   TimeToStruct(iTime(_Symbol, _Period, sh), dtCur);
   TimeToStruct(iTime(_Symbol, _Period, sh + 1), dtPrev);
   bool msNd = dtCur.hour == InpResetHour && dtCur.min == InpResetMin && (dtPrev.hour != InpResetHour || dtPrev.min != InpResetMin);

   if(!g_msInit)
     {
      g_msTr  = c >= o ? 1 : -1;
      g_msP1e = c >= o ? h : l;
      g_msP1o = c >= o ? l : h;
      g_msPp2 = c >= o ? h : l;
      g_msPp2Set = true;
      g_msInit = true;
     }
   if(msNd)
     {
      g_msTr  = c >= o ? 1 : -1;
      g_msSt  = 0;
      g_msP1e = c >= o ? h : l;
      g_msP1o = c >= o ? l : h;
      g_msP2eSet = false;
      g_msPp2 = c >= o ? h : l;
      g_msPp2Set = true;
      g_msPp1Set = false;
      g_msHp1 = false;
     }

   bool isP1up = false, isP1dn = false;

   if(g_msTr == 1)
     {
      if(g_msSt == 0 && h > g_msP1e)
        {
         g_msP1e = h; g_msP1o = l; g_msHp1 = true; isP1up = true;
        }
      if(g_msSt == 0 && h <= g_msP1e && l < g_msP1o)
        {
         g_msP2e = l; g_msP2eSet = true; g_msSt = 1;
        }
      if(g_msSt == 1 && l < g_msP2e)
         g_msP2e = l;
      if(g_msSt == 1 && c > g_msP1e)
        {
         g_msPp2 = g_msP2e; g_msPp2Set = true;
         g_msPp1Set = false; g_msHp1 = false;
         g_msP1e = h; g_msP1o = l; g_msP2eSet = false; g_msSt = 0;
        }
      bool tdn = (g_msPp2Set && c < g_msPp2) || (g_msHp1 && g_msPp1Set && c < g_msPp1);
      if(g_msSt == 1 && tdn && !(c > g_msP1e))
        {
         g_msPp2Set = false;
         g_msPp1 = g_msP1e; g_msPp1Set = true; g_msHp1 = true;
         g_msTr = -1; g_msSt = 0;
         g_msP1e = l; g_msP1o = h; g_msP2eSet = false;
        }
     }
   if(g_msTr == -1)
     {
      if(g_msSt == 0 && l < g_msP1e)
        {
         g_msP1e = l; g_msP1o = h; g_msHp1 = true; isP1dn = true;
        }
      if(g_msSt == 0 && l >= g_msP1e && h > g_msP1o)
        {
         g_msP2e = h; g_msP2eSet = true; g_msSt = 1;
        }
      if(g_msSt == 1 && h > g_msP2e)
         g_msP2e = h;
      if(g_msSt == 1 && c < g_msP1e)
        {
         g_msPp2 = g_msP2e; g_msPp2Set = true;
         g_msPp1Set = false; g_msHp1 = false;
         g_msP1e = l; g_msP1o = h; g_msP2eSet = false; g_msSt = 0;
        }
      bool tup = (g_msPp2Set && c > g_msPp2) || (g_msHp1 && g_msPp1Set && c > g_msPp1);
      if(g_msSt == 1 && tup && !(c < g_msP1e))
        {
         g_msPp2Set = false;
         g_msPp1 = g_msP1e; g_msPp1Set = true; g_msHp1 = true;
         g_msTr = 1; g_msSt = 0;
         g_msP1e = h; g_msP1o = l; g_msP2eSet = false;
        }
     }

   //--- 4) cycle de couleur vive
   bool vividUp = g_normVal >=  InpVividZone && g_strengthening;
   bool vividDn = g_normVal <= -InpVividZone && g_strengthening;

   if(vividUp && g_epDir != 1)  { g_epDir = 1;  g_refSet = false; g_refBar = -1; }
   if(vividDn && g_epDir != -1) { g_epDir = -1; g_refSet = false; g_refBar = -1; }

   if(g_epDir == 1 && vividUp && (!InpUseP1 || isP1up) && (!g_refSet || haH > g_refHi))
     { g_refHi = haH; g_refLo = haL; g_refSet = true; g_refBar = g_barCount; }
   if(g_epDir == -1 && vividDn && (!InpUseP1 || isP1dn) && (!g_refSet || haL < g_refLo))
     { g_refHi = haH; g_refLo = haL; g_refSet = true; g_refBar = g_barCount; }

   if(g_epDir != 0 && g_refSet && InpMaxWait > 0 && g_barCount - g_refBar > InpMaxWait)
     { g_epDir = 0; g_refSet = false; }

   g_fadeCnt = g_epDir == 1 ? (vividUp ? 0 : g_fadeCnt + 1) : g_epDir == -1 ? (vividDn ? 0 : g_fadeCnt + 1) : 0;
   if(g_epDir != 0 && g_fadeCnt >= InpCancelBars)
     { g_epDir = 0; g_refSet = false; }

   bool brkDn = g_epDir == 1  && g_refSet && g_barCount > g_refBar && (InpBreakOnClose ? haC < g_refLo : haL < g_refLo);
   bool brkUp = g_epDir == -1 && g_refSet && g_barCount > g_refBar && (InpBreakOnClose ? haC > g_refHi : haH > g_refHi);
   if(brkDn || brkUp)
     { g_epDir = 0; g_refSet = false; }

   //--- 5) croix de perte de momentum (valide uniquement en PnL positif)
   bool exitAfterBull = false, exitAfterBear = false;
   if(g_pendingExit == 1 && g_sigBar >= 0 && g_barCount > g_sigBar && g_momDnCnt >= InpCrossBars && c > g_sigPrice)
     { exitAfterBull = true; g_pendingExit = 0; }
   if(g_pendingExit == -1 && g_sigBar >= 0 && g_barCount > g_sigBar && g_momUpCnt >= InpCrossBars && c < g_sigPrice)
     { exitAfterBear = true; g_pendingExit = 0; }

   //--- 6) suivi du trade : stop sorti chez le broker ?
   ulong ticket; long ptype; double popen;
   bool havePos = GetOurPosition(ticket, ptype, popen);
   if(g_trOpen && !havePos)
     {
      // position close par le broker (SL initial ou SL break-even)
      RecordResult(g_trBE ? 0.0 : -1.0);
      DrawClose(iTime(_Symbol, _Period, sh), g_trBE ? g_trEnt : g_trSl,
                g_trBE ? "BE 0 R" : "-1 R",
                g_trBE ? clrGray : clrRed, false);
      g_trOpen = false;
     }

   //--- 7) gestion du trade actif : break-even puis sortie croix
   if(g_trOpen && havePos)
      DrawExtend(iTime(_Symbol, _Period, sh));
   if(g_trOpen && havePos && g_barCount > g_trStartBar)
     {
      if(InpUseBE && !g_trBE)
        {
         bool beNow = g_trDir == 1 ? (h >= g_trEnt + InpBeTrigger * g_trRisk)
                                   : (l <= g_trEnt - InpBeTrigger * g_trRisk);
         if(beNow)
           {
            if(ModifySL(ticket, g_trEnt))
              {
               g_trBE = true;
               DrawBE(iTime(_Symbol, _Period, sh), g_trEnt);
               Print("HA Sig EA : break-even active, SL ramene a l'entree");
              }
           }
        }
      bool crossExit = g_trDir == 1 ? exitAfterBull : exitAfterBear;
      if(crossExit)
        {
         double res = g_trDir * (c - g_trEnt) / g_trRisk;
         if(CloseByTicket(ticket))
           {
            RecordResult(res);
            string resTxt = (res >= 0 ? "+" : "") + DoubleToString(res, 2) + " R";
            color  resCol = res > 0.01 ? clrLime : res < -0.01 ? clrRed : clrGray;
            DrawClose(iTime(_Symbol, _Period, sh), c, resTxt, resCol, true);
            g_trOpen = false;
           }
        }
     }

   //--- 8) nouveaux signaux : uniquement sans trade en cours
   bool sigBull = brkUp && !g_trOpen;
   bool sigBear = brkDn && !g_trOpen;

   int openDir = sigBull ? 1 : sigBear ? -1 : 0;
   if(openDir != 0)
     {
      double ent = c; // reference logique ; execution au marche a l'ouverture suivante
      double sl  = openDir == 1 ? LowestLow(sh, InpSlLen) : HighestHigh(sh, InpSlLen);
      double risk = MathAbs(ent - sl);
      if(risk > 0)
        {
         double lots = LotsForRisk(risk);
         bool ok = OpenMarket(openDir, lots, sl);
         if(ok)
           {
            g_trId++;
            DrawOpen(iTime(_Symbol, _Period, sh), ent, sl, openDir);
            g_trOpen = true;
            g_trDir = openDir;
            g_trEnt = ent;
            g_trSl = sl;
            g_trRisk = risk;
            g_trBE = false;
            g_trStartBar = g_barCount;
            // armement de la croix sur le signal execute
            g_pendingExit = openDir;
            g_sigBar = g_barCount;
            g_sigPrice = ent;
            PrintFormat("HA Sig EA : %s | entree ref %.5f | SL %.5f | risque %.5f | lots %.2f",
                        openDir == 1 ? "LONG" : "SHORT", ent, sl, risk, lots);
           }
        }
     }

   UpdateComment();
  }

//=================== TICK ===========================================
void OnTick()
  {
   datetime t0 = iTime(_Symbol, _Period, 0);
   if(t0 == g_lastBarTime)
      return;              // pas de nouvelle bougie : le stop reel est chez le broker
   g_lastBarTime = t0;
   // s'assure qu'il y a assez d'historique pour les calculs
   if(Bars(_Symbol, _Period) < InpKcLength * 2 + InpNormLen + 5)
      return;
   ProcessClosedBar();
  }
//+------------------------------------------------------------------+
