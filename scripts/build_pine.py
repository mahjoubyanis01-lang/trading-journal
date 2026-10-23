#!/usr/bin/env python3
"""Génère l'indicateur TradingView (Pine Script v6) « Signaux ES/NQ » :
signaux d'achat / vente validés par backtest (calculés par TradingView) +
couche optionnelle « Plan du jour » GEX :
les points de retournement potentiels de la séance pour ES/MES et NQ/MNQ.

Les niveaux viennent du snapshot CBOE qui a verrouillé la journée
(data/levels/<SYM>/<jour>.json -> source_snapshot). Ce snapshot ne change
plus : le plan est donc identique toute la séance.

Méthode (par symbole) :
- concentration de gamma par strike = |GEX calls| + |GEX puts| : là où les
  dealers couvrent le plus, le prix a tendance à buter / rebondir ;
- fenêtre intraday = max(2 x expected move, 1,2 %) du spot (max 3 %) ;
- R1/R2 = les 2 plus fortes concentrations au-dessus du spot, S1/S2 en
  dessous (espacement minimum 0,3 %), R1/S1 = les plus proches du prix ;
- force 1-3 étoiles selon le poids relatif, +1 en confluence avec un mur
  0DTE, un mur global ou une borne de l'expected move ;
- pivot = gamma flip s'il est à portée ; bornes = expected move du jour.

Sorties : tradingview/GEX_Levels_ES_NQ.pine, tradingview/levels.json
Usage   : python3 scripts/build_pine.py
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEVELS = ROOT / "data" / "levels"
OUT = ROOT / "tradingview"
PINE_FILE = OUT / "GEX_Levels_ES_NQ.pine"
DATASETS = ["SPX", "SPY", "NDX", "QQQ"]


def latest_levels(sym: str):
    days_file = LEVELS / sym / "days.json"
    if not days_file.exists():
        return None
    days = json.loads(days_file.read_text())["days"]
    for day in reversed(days):
        f = LEVELS / sym / f"{day}.json"
        if f.exists():
            return json.loads(f.read_text())
    return None


def expected_move(lv: dict):
    n0 = lv.get("nearest_expiry") or {}
    if n0.get("em_up") is not None:
        return n0["em_up"], n0["em_down"], "straddle 0DTE"
    if lv.get("em_iv"):
        return lv["spot"] + lv["em_iv"], lv["spot"] - lv["em_iv"], "IV 30 j"
    return None, None, "—"


def reversal_plan(lv: dict) -> dict:
    snap = json.loads((ROOT / lv["source_snapshot"]).read_text())
    spot = snap["spot"]
    em_up, em_down, em_src = expected_move(lv)
    em = (em_up - em_down) / 2 if em_up is not None else spot * 0.008
    win = min(max(2 * em, 0.012 * spot), 0.03 * spot)
    spacing = 0.003 * spot
    total = {
        k: abs(c) + abs(p)
        for k, c, p in zip(snap["strikes"], snap["call_gex"], snap["put_gex"])
    }

    def pick(cands):
        chosen = []
        for k, v in sorted(cands, key=lambda kv: kv[1], reverse=True):
            if all(abs(k - c) >= spacing for c, _ in chosen):
                chosen.append((k, v))
            if len(chosen) == 2:
                break
        return sorted(chosen, key=lambda kv: abs(kv[0] - spot))

    above = pick([(k, v) for k, v in total.items() if spot < k <= spot + win])
    below = pick([(k, v) for k, v in total.items() if spot - win <= k < spot])
    ref = max([v for _, v in above + below] or [1.0])
    n0 = lv.get("nearest_expiry") or {}
    confluences = {
        "mur 0DTE": [n0.get("call_wall"), n0.get("put_wall")],
        "mur global": [lv.get("call_wall"), lv.get("put_wall")],
        "borne EM": [em_up, em_down],
    }

    def level(kv):
        if kv is None:
            return None
        k, v = kv
        r = v / ref
        stars = 3 if r >= 0.7 else 2 if r >= 0.4 else 1
        tags = [name for name, xs in confluences.items()
                if any(x is not None and abs(k - x) <= 0.0015 * spot for x in xs)]
        if tags:
            stars = min(3, stars + 1)
        return {"strike": k, "stars": stars, "gamma_musd": round(v), "confluence": tags}

    flip = lv.get("flip")
    return {
        "spot": spot,
        "window": round(win, 2),
        "R1": level(above[0] if len(above) > 0 else None),
        "R2": level(above[1] if len(above) > 1 else None),
        "S1": level(below[0] if len(below) > 0 else None),
        "S2": level(below[1] if len(below) > 1 else None),
        "pivot": flip if flip is not None and abs(flip - spot) <= 1.5 * win else None,
        "em_up": em_up,
        "em_down": em_down,
        "em_source": em_src,
    }


def heat_rows(lv: dict, pct: float = 0.025, max_rows: int = 60):
    """Profil GEX net autour du spot (+/- pct) pour la heatmap TradingView.
    Au-delà de max_rows strikes, regroupement en tranches de largeur égale."""
    snap = json.loads((ROOT / lv["source_snapshot"]).read_text())
    spot = snap["spot"]
    rows = [(k, c + p) for k, c, p in zip(snap["strikes"], snap["call_gex"], snap["put_gex"])
            if abs(k - spot) <= pct * spot]
    if len(rows) > max_rows:
        lo, hi = rows[0][0], rows[-1][0]
        w = (hi - lo) / max_rows
        bins = {}
        for k, g in rows:
            i = min(max_rows - 1, int((k - lo) / w))
            bins.setdefault(i, [0.0, 0.0, 0])
            bins[i][0] += g
            bins[i][1] += k
            bins[i][2] += 1
        rows = [(v[1] / v[2], v[0]) for _, v in sorted(bins.items())]
    return [round(k, 2) for k, _ in rows], [round(g, 1) for _, g in rows]


def pf(v) -> str:
    if v is None:
        return "float(na)"
    s = repr(round(float(v), 4))
    return s if ("." in s or "e" in s) else s + ".0"


def dataset_block(sym: str, lv) -> tuple[str, dict]:
    if lv is None:
        plan = None
        vals = {"DAY": '""', "LOCK": '""', "NET": "float(na)", "EMSRC": '"—"'}
        for key in ("R2", "R1", "S1", "S2"):
            vals[key] = "float(na)"
            vals[key + "S"] = "0"
        vals.update({"PIV": "float(na)", "EMH": "float(na)", "EML": "float(na)"})
        summary = {"symbol": sym, "available": False}
    else:
        plan = reversal_plan(lv)
        vals = {
            "DAY": f'"{lv["day"]}"',
            "LOCK": f'"{lv["locked_at"][11:16]}"',
            "NET": pf(lv.get("net_gex")),
            "EMSRC": f'"{plan["em_source"]}"',
        }
        for key in ("R2", "R1", "S1", "S2"):
            lvl = plan[key]
            vals[key] = pf(lvl["strike"] if lvl else None)
            vals[key + "S"] = str(lvl["stars"] if lvl else 0)
        vals.update({"PIV": pf(plan["pivot"]), "EMH": pf(plan["em_up"]), "EML": pf(plan["em_down"])})
        summary = {
            "symbol": sym, "available": True, "day": lv["day"], "locked_at": lv["locked_at"],
            "net_gex": lv.get("net_gex"), "plan": plan,
        }
    lines = [f"{sym}_{k:<5} = {v}" for k, v in vals.items()]
    hk, hg = heat_rows(lv) if lv is not None else ([], [])
    lines.append(f"var array<float> {sym}_HK = " + (f"array.from({', '.join(pf(x) for x in hk)})" if hk else "array.new<float>()"))
    lines.append(f"var array<float> {sym}_HG = " + (f"array.from({', '.join(pf(x) for x in hg)})" if hg else "array.new<float>()"))
    if lv is not None:
        summary["heat"] = {"strikes": hk, "net_gex": hg}
    return "\n".join(lines), summary


PINE_TEMPLATE = r'''//@version=6
// ════════════════════════════════════════════════════════════════════════
//  TRADING ES / NQ — biais de séance, niveaux clés, signaux, heatmap GEX
//  Détection automatique : ES, MES (S&P 500) · NQ, MNQ (Nasdaq 100)
//
//  SIGNAL A — cassure du range d'ouverture dans le sens de Londres (≈ 0,8/jour ES+NQ)
//   · Biais de séance = sens de la séance de Londres (2h00 -> 9h25 New York).
//   · Range d'ouverture = plus haut / plus bas de 9h30 à 9h45.
//   · Première clôture 5 min hors du range avant 11h30 : si elle est dans le
//     sens du biais -> ACHAT / VENTE ; sinon, pas de trade ce jour-là.
//   · Stop au milieu du range, objectif 2R, sortie au plus tard à 15h55.
//  SIGNAL B — cassure acceptée + retest du plus haut / plus bas de la veille
//   dans le sens de la tendance 20 jours (bougies 1 h, rare).
//  Les deux moteurs sont calculés par TradingView en temps réel, sans repeindre.
//
//  Backtests de référence (frais inclus) :
//{stats_comment}
//  Les performances passées ne garantissent pas les résultats futurs.
//
//  Couches du jour (heatmap GEX, plan GEX, annonces macro US) : données du {day},
//  à recopier chaque jour depuis
//  https://mahjoubyanis01-lang.github.io/trading-journal/tradingview.html
// ════════════════════════════════════════════════════════════════════════
indicator("Trading ES/NQ — biais, niveaux, signaux, heatmap", shorttitle = "ES/NQ Pro", overlay = true, max_lines_count = 400, max_labels_count = 400, max_boxes_count = 300)

// ── BACKTESTS DE RÉFÉRENCE (générés automatiquement) ─────────────────────
{stats}

// ── PLAN GEX + HEATMAP DU JOUR (générés automatiquement) ─────────────────
{data}

// ── ANNONCES MACRO US DU JOUR (générées automatiquement) ─────────────────
{events}

// Jours fériés et séances écourtées NYSE : aucun signal A
var array<string> HOLIDAYS = array.from("2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-11-27", "2026-12-24", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-11-26", "2027-12-24")

// ── PARAMÈTRES ───────────────────────────────────────────────────────────
mktMode    = input.string("Auto", "Marché", options = ["Auto", "S&P 500 (ES / MES)", "Nasdaq 100 (NQ / MNQ)"])
showSigA   = input.bool(true, "Signal A — cassure d'ouverture (biais Londres)", group = "Signaux")
shortMode  = input.string("Seulement en tendance baissière (recommandé)", "Ventes du signal A", options = ["Seulement en tendance baissière (recommandé)", "Toujours (plus de signaux, moins fiables)"], group = "Signaux")
showSigB   = input.bool(true, "Signal B — retest PDH / PDL (tendance)", group = "Signaux")
showSess   = input.bool(true, "Niveaux de séance (Asie, Londres, veille, range d'ouverture)", group = "Niveaux")
showHeat   = input.bool(true, "Heatmap GEX en dégradé", group = "Options CBOE (du jour)")
heatAlpha  = input.int(55, "Intensité max de la heatmap (transparence)", minval = 0, maxval = 95, group = "Options CBOE (du jour)")
showGex    = input.bool(false, "Plan GEX R1/R2/S1/S2 (non validé)", group = "Options CBOE (du jour)")
showEvents = input.bool(true, "Annonces macro US du jour", group = "Macro")
showTable  = input.bool(true, "Tableau", group = "Affichage")
colBuy     = input.color(#0ca30c, "Achat / support", group = "Couleurs")
colSell    = input.color(#e34948, "Vente / résistance", group = "Couleurs")
colLv      = input.color(#9085e9, "Veille (PDH / PDL)", group = "Couleurs")
colLon     = input.color(#2a78d6, "Londres", group = "Couleurs")
colAsia    = input.color(#898781, "Asie", group = "Couleurs")
colPiv     = input.color(#eda100, "Range d'ouverture / pivot", group = "Couleurs")
colHeatPos = input.color(#2a78d6, "Heatmap : gamma positif", group = "Couleurs")
colHeatNeg = input.color(#e34948, "Heatmap : gamma négatif", group = "Couleurs")

// ── MARCHÉ ───────────────────────────────────────────────────────────────
string root = syminfo.root
string tk   = syminfo.ticker
bool isSP = root == "ES" or root == "MES" or tk == "SPX" or tk == "SPY" or str.contains(tk, "US500") or str.contains(tk, "SPX500") or str.contains(tk, "SP500")
bool isNQ = root == "NQ" or root == "MNQ" or tk == "NDX" or tk == "QQQ" or str.contains(tk, "NAS100") or str.contains(tk, "US100") or str.contains(tk, "NDX100") or str.contains(tk, "USTEC")
string mkt = mktMode == "S&P 500 (ES / MES)" ? "SP" : mktMode == "Nasdaq 100 (NQ / MNQ)" ? "NQ" : isSP ? "SP" : isNQ ? "NQ" : "NONE"
bool isFut = root == "ES" or root == "MES" or root == "NQ" or root == "MNQ"
bool tfA = timeframe.isintraday and timeframe.in_seconds() <= 300
bool tfB = timeframe.isintraday and timeframe.in_seconds() <= 3600
bool  nqP    = mkt == "NQ"
float A_MINR = nqP ? 8.0 : 2.0
float A_MAXR = nqP ? 100.0 : 25.0
float P_TOL  = nqP ? 8.0 : 2.0
float P_STOP = nqP ? 24.0 : 6.0
float P_MINR = nqP ? 12.0 : 3.0
float P_MAXR = nqP ? 120.0 : 30.0
float P_COST = nqP ? 2.0 : 0.5

px(float v) => na(v) ? "—" : str.tostring(math.round_to_mintick(v))
rr(float v) => (v >= 0 ? "+" : "") + str.tostring(v, "0.0") + "R"

// ── MOTEUR B : retest PDH / PDL dans la tendance (bougies 1 h) ───────────
// Même ordre d'opérations que backtest/signals_backtest.py.
// Les sorties d'événements sont décalées d'une bougie ([1]) et lues avec
// lookahead_on : aucun signal ne peut apparaître avant la clôture de sa bougie.
engineB(float tol, float stopOff, float minRisk, float maxRisk, float cost) =>
    int h = hour(time, "America/New_York")
    int dw = dayofweek(time, "America/New_York")
    bool rth = h >= 10 and h <= 15 and dw != dayofweek.saturday and dw != dayofweek.sunday
    string d = str.format_time(time, "yyyy-MM-dd", "America/New_York")
    var string rthDay = ""
    var float curH = na
    var float curL = na
    var float curC = na
    var float pdh = na
    var float pdl = na
    var array<float> closes = array.new<float>()
    var int trend = 0
    var float c1 = na
    var float c2 = na
    var int stH = 0
    var int stL = 0
    var int sdH = 0
    var int sdL = 0
    var bool done = false
    var int tSide = 0
    var float tEntry = na
    var float tStop = na
    var float tTgt = na
    var float tRisk = na
    var float tLevel = na
    var int nT = 0
    var int nW = 0
    var float sumR = 0.0
    int sig = 0
    int xCode = 0
    float xPx = na
    float xR = na
    if rth
        bool newDay = d != rthDay
        if newDay and tSide != 0
            xCode := 4
            xPx := curC
        if newDay
            if rthDay != ""
                pdh := curH
                pdl := curL
                array.push(closes, curC)
                int n = array.size(closes)
                if n >= 20
                    float s = 0.0
                    for j = n - 20 to n - 1
                        s += array.get(closes, j)
                    trend := curC > s / 20 ? 1 : -1
            rthDay := d
            curH := high
            curL := low
            c1 := na
            c2 := na
            stH := 0
            stL := 0
            done := false
        if tSide != 0 and xCode == 0
            if tSide > 0
                if low <= tStop
                    xCode := 2
                    xPx := tStop
                else if high >= tTgt
                    xCode := 1
                    xPx := tTgt
            else
                if high >= tStop
                    xCode := 2
                    xPx := tStop
                else if low <= tTgt
                    xCode := 1
                    xPx := tTgt
            if xCode == 0 and h == 15
                xCode := 3
                xPx := close
        if xCode != 0
            xR := (tSide * (xPx - tEntry) - cost) / tRisk
            nT += 1
            sumR += xR
            if xR > 0
                nW += 1
            tSide := 0
        if h <= 14 and not done and not na(pdh) and trend != 0
            if stH == 0
                if not na(c2) and c2 <= pdh and c1 > pdh and close > pdh
                    stH := 1
                    sdH := 1
                else if not na(c2) and c2 >= pdh and c1 < pdh and close < pdh
                    stH := 1
                    sdH := -1
            else if stH == 1
                if (sdH > 0 and low <= pdh + tol) or (sdH < 0 and high >= pdh - tol)
                    if sdH * (close - pdh) > 0 and sdH == trend
                        float stp = pdh - sdH * stopOff
                        float rk = math.abs(close - stp)
                        if rk >= minRisk and rk <= maxRisk
                            sig := sdH
                            tSide := sdH
                            tEntry := close
                            tStop := stp
                            tRisk := rk
                            tTgt := close + sdH * 2 * rk
                            tLevel := pdh
                            done := true
                    stH := 2
            if not done
                if stL == 0
                    if not na(c2) and c2 <= pdl and c1 > pdl and close > pdl
                        stL := 1
                        sdL := 1
                    else if not na(c2) and c2 >= pdl and c1 < pdl and close < pdl
                        stL := 1
                        sdL := -1
                else if stL == 1
                    if (sdL > 0 and low <= pdl + tol) or (sdL < 0 and high >= pdl - tol)
                        if sdL * (close - pdl) > 0 and sdL == trend
                            float stp = pdl - sdL * stopOff
                            float rk = math.abs(close - stp)
                            if rk >= minRisk and rk <= maxRisk
                                sig := sdL
                                tSide := sdL
                                tEntry := close
                                tStop := stp
                                tRisk := rk
                                tTgt := close + sdL * 2 * rk
                                tLevel := pdl
                                done := true
                        stL := 2
        curH := math.max(curH, high)
        curL := math.min(curL, low)
        curC := close
        c2 := c1
        c1 := close
    int sigT = sig != 0 ? time : na
    int xT = xCode != 0 ? time : na
    int pend = rth and h <= 14 and not done and trend != 0 ? (stH == 1 and sdH == trend ? sdH : stL == 1 and sdL == trend ? sdL : 0) : 0
    float pendLv = stH == 1 and sdH == trend ? pdh : pdl
    float dispH = rth ? pdh : curH
    float dispL = rth ? pdl : curL
    [sigT[1], sig[1], tEntry[1], tStop[1], tTgt[1], tLevel[1], xT[1], xCode[1], xPx[1], xR[1], dispH, dispL, trend, pend[1], pendLv[1], nT[1], nW[1], sumR[1]]

// ── MOTEUR A : cassure du range d'ouverture dans le sens de Londres (bougies 5 min) ──
// Même ordre d'opérations que backtest/intraday/orb_london.py (référence vérifiée trade par trade).
engineA(float minRisk, float maxRisk, float cost, bool shortFilter) =>
    int m = hour(time, "America/New_York") * 60 + minute(time, "America/New_York")
    int dw = dayofweek(time, "America/New_York")
    string d = str.format_time(time, "yyyy-MM-dd", "America/New_York")
    bool wk = dw != dayofweek.saturday and dw != dayofweek.sunday
    var string curD = ""
    var float lonO = na
    var float lonC = na
    var float lonH = na
    var float lonL = na
    var float asH = na
    var float asL = na
    var float orH = na
    var float orL = na
    var int bias = 0
    var bool decided = false
    var float lastRth = na
    var int rthN = 0
    var int orN = 0
    var array<float> rthCloses = array.new<float>()
    var int trend = 0
    var int tSide = 0
    var float tE = na
    var float tS = na
    var float tT = na
    var float tR = na
    var int nT = 0
    var int nW = 0
    var float sumR = 0.0
    int sig = 0
    int xCode = 0
    float xPx = na
    float xR = na
    // Asie (18h-2h) : remise à zéro à 18h
    if m == 1080
        asH := high
        asL := low
    else if m > 1080 or m < 120
        asH := math.max(nz(asH, high), high)
        asL := math.min(nz(asL, low), low)
    // Nouvelle journée à partir de 2h00 NY
    if wk and m >= 120 and m < 960 and d != curD
        if tSide != 0
            xCode := 4
            xPx := close[1]
        if not na(lastRth) and rthN >= 70 and orN >= 3
            array.push(rthCloses, lastRth)
            int n = array.size(rthCloses)
            if n >= 20
                float sm = 0.0
                for j = n - 20 to n - 1
                    sm += array.get(rthCloses, j)
                trend := lastRth > sm / 20 ? 1 : -1
        lastRth := na
        rthN := 0
        orN := 0
        curD := d
        lonO := na
        lonC := na
        lonH := na
        lonL := na
        orH := na
        orL := na
        bias := 0
        decided := false
    if wk and d == curD
        if m >= 120 and m < 565
            lonO := na(lonO) ? open : lonO
            lonC := close
            lonH := math.max(nz(lonH, high), high)
            lonL := math.min(nz(lonL, low), low)
        if m >= 570 and m < 960
            lastRth := close
            rthN += 1
        if m >= 570 and m < 585
            orN += 1
            orH := math.max(nz(orH, high), high)
            orL := math.min(nz(orL, low), low)
        // gestion du trade ouvert
        if tSide != 0 and xCode == 0 and m >= 570
            if m >= 955
                xCode := 3
                xPx := open
            else if tSide > 0
                if low <= tS
                    xCode := 2
                    xPx := tS
                else if high >= tT
                    xCode := 1
                    xPx := tT
            else
                if high >= tS
                    xCode := 2
                    xPx := tS
                else if low <= tT
                    xCode := 1
                    xPx := tT
        if xCode != 0
            xR := (tSide * (xPx - tE) - cost) / tR
            nT += 1
            sumR += xR
            if xR > 0
                nW += 1
            tSide := 0
        // signal : première clôture 5 min hors du range 9h30-9h45, avant 11h30
        if not decided and m >= 585 and m < 690 and not na(orH)
            bias := na(lonO) ? 0 : lonC > lonO ? 1 : lonC < lonO ? -1 : 0
            int s = close > orH ? 1 : close < orL ? -1 : 0
            if s != 0
                decided := true
                if bias != 0 and s == bias and not (s < 0 and shortFilter and trend != -1)
                    float st = (orH + orL) / 2
                    float rk = math.abs(close - st)
                    if rk >= minRisk and rk <= maxRisk
                        sig := s
                        tSide := s
                        tE := close
                        tS := st
                        tR := rk
                        tT := close + s * 2 * rk
    int curBias = na(lonO) ? 0 : lonC > lonO ? 1 : lonC < lonO ? -1 : 0
    int sigT = sig != 0 ? time : na
    int xT = xCode != 0 ? time : na
    [sigT[1], sig[1], tE[1], tS[1], tT[1], xT[1], xCode[1], xPx[1], xR[1], nT[1], nW[1], sumR[1], curBias[1], lonH[1], lonL[1], asH[1], asL[1], orH[1], orL[1], decided[1], trend]

// ── APPELS DES MOTEURS (sorties décalées d'une bougie : aucun signal avant clôture) ──
[aSigT, aSide, aE, aS, aT, aXT, aXCode, aXPx, aXR, aN, aW, aSum, aBias, gLonH, gLonL, gAsH, gAsL, gOrH, gOrL, aDecided, aTrend] = request.security(syminfo.tickerid, "5", engineA(A_MINR, A_MAXR, P_COST, shortMode == "Seulement en tendance baissière (recommandé)"), lookahead = barmerge.lookahead_on)
[bSigT, bSide, bE, bS, bT, bLv, bXT, bXCode, bXPx, bXR, dH, dL, trendD, bPendSide, bPendLv, bN, bW, bSum] = request.security(syminfo.tickerid, "60", engineB(P_TOL, P_STOP, P_MINR, P_MAXR, P_COST), lookahead = barmerge.lookahead_on)
string todayNY = str.format_time(time, "yyyy-MM-dd", "America/New_York")
bool holiday = array.includes(HOLIDAYS, todayNY)

// ── NIVEAUX DE SÉANCE ────────────────────────────────────────────────────
bool sessOn = showSess and isFut and tfB
int mNY = hour(time, "America/New_York") * 60 + minute(time, "America/New_York")
plot(sessOn and dH == dH[1] ? dH : na, "PDH (veille)", color = colLv, linewidth = 2, style = plot.style_linebr)
plot(sessOn and dL == dL[1] ? dL : na, "PDL (veille)", color = colLv, linewidth = 2, style = plot.style_linebr)
plot(sessOn and mNY >= 565 and mNY < 960 and gLonH == gLonH[1] ? gLonH : na, "Londres haut", color = colLon, linewidth = 1, style = plot.style_linebr)
plot(sessOn and mNY >= 565 and mNY < 960 and gLonL == gLonL[1] ? gLonL : na, "Londres bas", color = colLon, linewidth = 1, style = plot.style_linebr)
plot(sessOn and mNY >= 120 and mNY < 960 and gAsH == gAsH[1] ? gAsH : na, "Asie haut", color = colAsia, linewidth = 1, style = plot.style_linebr)
plot(sessOn and mNY >= 120 and mNY < 960 and gAsL == gAsL[1] ? gAsL : na, "Asie bas", color = colAsia, linewidth = 1, style = plot.style_linebr)
plot(sessOn and mNY >= 585 and mNY < 960 and gOrH == gOrH[1] ? gOrH : na, "Range d'ouverture haut", color = colPiv, linewidth = 2, style = plot.style_linebr)
plot(sessOn and mNY >= 585 and mNY < 960 and gOrL == gOrL[1] ? gOrL : na, "Range d'ouverture bas", color = colPiv, linewidth = 2, style = plot.style_linebr)
bgcolor(sessOn and mNY >= 570 and mNY < 585 ? color.new(colPiv, 92) : na, title = "Range d'ouverture 9h30-9h45")

// ── SIGNAL A ─────────────────────────────────────────────────────────────
bool sigAOn = showSigA and isFut and tfA and mkt != "NONE"
var int lastAT = 0
var int lastAX = 0
var line aLE = na
var line aLS = na
var line aLT = na
var bool aIn = false
var string aTxt = "aucun sur l'historique chargé"
bool newA = sigAOn and not na(aSigT) and aSigT != lastAT and not holiday
bool newABuy = newA and aSide > 0
bool newASell = newA and aSide < 0
if newA
    lastAT := aSigT
    color c = aSide > 0 ? colBuy : colSell
    label.new(bar_index, aSide > 0 ? low : high, (aSide > 0 ? "▲ ACHAT A" : "▼ VENTE A") + "\ncassure d'ouverture · biais Londres\nentrée " + px(aE) + "  stop " + px(aS) + "\nobjectif " + px(aT) + " (2R)", yloc = aSide > 0 ? yloc.belowbar : yloc.abovebar, style = aSide > 0 ? label.style_label_up : label.style_label_down, color = c, textcolor = color.white, size = size.normal)
    aLE := line.new(bar_index, aE, bar_index + 1, aE, color = c, width = 2)
    aLS := line.new(bar_index, aS, bar_index + 1, aS, color = colSell, style = line.style_dashed)
    aLT := line.new(bar_index, aT, bar_index + 1, aT, color = colBuy, style = line.style_dashed)
    aIn := true
    aTxt := (aSide > 0 ? "ACHAT " : "VENTE ") + str.format_time(aSigT, "dd/MM HH:mm", "America/New_York") + " NY · en cours"
if aIn
    line.set_x2(aLE, bar_index)
    line.set_x2(aLS, bar_index)
    line.set_x2(aLT, bar_index)
if sigAOn and not na(aXT) and aXT != lastAX
    lastAX := aXT
    if aIn
        aIn := false
        string res = (aXCode == 1 ? "✓ objectif " : aXCode == 2 ? "✗ stop " : "sortie 15h55 ") + rr(aXR)
        label.new(bar_index, aXPx, res, style = label.style_label_left, color = color.new(aXR >= 0 ? colBuy : colSell, 75), textcolor = aXR >= 0 ? colBuy : colSell, size = size.small)
        aTxt := str.replace(aTxt, "en cours", res)

// ── SIGNAL B ─────────────────────────────────────────────────────────────
bool sigBOn = showSigB and isFut and tfB and mkt != "NONE"
var int lastBT = 0
var int lastBX = 0
var line bLE = na
var line bLS = na
var line bLT = na
var bool bIn = false
var string bTxt = "aucun sur l'historique chargé"
bool newB = sigBOn and not na(bSigT) and bSigT != lastBT
bool newBBuy = newB and bSide > 0
bool newBSell = newB and bSide < 0
if newB
    lastBT := bSigT
    color c = bSide > 0 ? colBuy : colSell
    string lvName = bLv == dH ? "PDH" : "PDL"
    label.new(bar_index, bSide > 0 ? low : high, (bSide > 0 ? "▲ ACHAT B" : "▼ VENTE B") + "\nretest " + lvName + " " + px(bLv) + "\nentrée " + px(bE) + "  stop " + px(bS) + "\nobjectif " + px(bT) + " (2R)", yloc = bSide > 0 ? yloc.belowbar : yloc.abovebar, style = bSide > 0 ? label.style_label_up : label.style_label_down, color = c, textcolor = color.white, size = size.normal)
    bLE := line.new(bar_index, bE, bar_index + 1, bE, color = c, width = 2)
    bLS := line.new(bar_index, bS, bar_index + 1, bS, color = colSell, style = line.style_dashed)
    bLT := line.new(bar_index, bT, bar_index + 1, bT, color = colBuy, style = line.style_dashed)
    bIn := true
    bTxt := (bSide > 0 ? "ACHAT " : "VENTE ") + str.format_time(bSigT, "dd/MM HH:mm", "America/New_York") + " NY · en cours"
if bIn
    line.set_x2(bLE, bar_index)
    line.set_x2(bLS, bar_index)
    line.set_x2(bLT, bar_index)
if sigBOn and not na(bXT) and bXT != lastBX
    lastBX := bXT
    if bIn
        bIn := false
        string res = (bXCode == 1 ? "✓ objectif " : bXCode == 2 ? "✗ stop " : "sortie 16h ") + rr(bXR)
        label.new(bar_index, bXPx, res, style = label.style_label_left, color = color.new(bXR >= 0 ? colBuy : colSell, 75), textcolor = bXR >= 0 ? colBuy : colSell, size = size.small)
        bTxt := str.replace(bTxt, "en cours", res)

// ── PLAN GEX (couche optionnelle) ────────────────────────────────────────
string srcName = mkt == "NQ" ? "NDX" : "SPX"
string srcTv   = mkt == "NQ" ? "NASDAQ:NDX" : "SP:SPX"
string altTv   = mkt == "NQ" ? "TVC:NDX" : "TVC:SPX"
pickF(string k, float a, float b) => k == "SPX" ? a : b
pickI(string k, int a, int b) => k == "SPX" ? a : b
pickS(string k, string a, string b) => k == "SPX" ? a : b
string gDay = pickS(srcName, SPX_DAY, NDX_DAY)
float gR2 = pickF(srcName, SPX_R2, NDX_R2)
float gR1 = pickF(srcName, SPX_R1, NDX_R1)
float gS1 = pickF(srcName, SPX_S1, NDX_S1)
float gS2 = pickF(srcName, SPX_S2, NDX_S2)
int   sR2 = pickI(srcName, SPX_R2S, NDX_R2S)
int   sR1 = pickI(srcName, SPX_R1S, NDX_R1S)
int   sS1 = pickI(srcName, SPX_S1S, NDX_S1S)
int   sS2 = pickI(srcName, SPX_S2S, NDX_S2S)
float gPiv = pickF(srcName, SPX_PIV, NDX_PIV)
float gEmH = pickF(srcName, SPX_EMH, NDX_EMH)
float gEmL = pickF(srcName, SPX_EML, NDX_EML)

// Écart futures / indice : moyenne 9h30-9h45 NY, gelée pour la séance.
float idxMain = request.security(srcTv, timeframe.period, close, gaps = barmerge.gaps_on, ignore_invalid_symbol = true)
float idxAlt  = request.security(altTv, timeframe.period, close, gaps = barmerge.gaps_on, ignore_invalid_symbol = true)
float idx = na(idxMain) ? idxAlt : idxMain
var float  ratioFinal = na
var float  ratioPrev  = na
var float  accSum     = 0.0
var int    accN       = 0
var string accDay     = ""
var bool   frozen     = false
var int    dayStart   = na
bool justFrozen = false
if session.isfirstbar
    dayStart := time
if not na(idx) and idx > 0
    string nyDay = str.format_time(time, "yyyy-MM-dd", "America/New_York")
    int hmNy = hour(time, "America/New_York") * 60 + minute(time, "America/New_York")
    if nyDay != accDay
        ratioPrev := frozen ? ratioFinal : accN > 0 ? accSum / accN : ratioPrev
        accDay := nyDay
        accSum := 0.0
        accN := 0
        frozen := false
        ratioFinal := na
    if not frozen
        if hmNy < 9 * 60 + 45 or accN == 0
            accSum += close / idx
            accN += 1
        if hmNy >= 9 * 60 + 45
            ratioFinal := accSum / accN
            frozen := true
            justFrozen := true
float conv = frozen ? ratioFinal : not na(ratioPrev) ? ratioPrev : accN > 0 ? accSum / accN : na

stars(int s) => s >= 3 ? "★★★" : s == 2 ? "★★" : s == 1 ? "★" : ""
var array<box>   gBx = array.new<box>()
var array<line>  gLn = array.new<line>()
var array<label> gLb = array.new<label>()

gZone(float y, string name, int s, color col, int xs, int xl) =>
    if not na(y)
        float hh = y * 0.0004
        array.push(gBx, box.new(xs, y + hh, xl, y - hh, xloc = xloc.bar_time, extend = extend.right, border_color = color.new(col, 40), bgcolor = color.new(col, 88 - 6 * s)))
        array.push(gLb, label.new(xl, y, "GEX " + name + " " + stars(s) + "  " + px(y), xloc = xloc.bar_time, style = label.style_label_left, color = color.new(col, 82), textcolor = col, size = size.small))

gLine(float y, string name, color col, string sty, int xs, int xl) =>
    if not na(y)
        array.push(gLn, line.new(xs, y, xl, y, xloc = xloc.bar_time, extend = extend.right, color = col, width = 1, style = sty))
        array.push(gLb, label.new(xl, y, name + "  " + px(y), xloc = xloc.bar_time, style = label.style_label_left, color = color.new(col, 85), textcolor = col, size = size.small))

// ── HEATMAP GEX (dégradé) ────────────────────────────────────────────────
// Un rang par strike autour du prix : bleu = gamma positif (marché amorti,
// aimant / rebond), rouge = gamma négatif (accélérations). Intensité ∝ |GEX|.
array<float> hK = srcName == "SPX" ? SPX_HK : NDX_HK
array<float> hG = srcName == "SPX" ? SPX_HG : NDX_HG
var array<box> hBx = array.new<box>()

drawHeat(int xs, int xl) =>
    while array.size(hBx) > 0
        box.delete(array.pop(hBx))
    int n = array.size(hK)
    if showHeat and not na(conv) and n > 1
        float mx = 0.0
        for g in hG
            mx := math.max(mx, math.abs(g))
        for i = 0 to n - 1
            float k = array.get(hK, i)
            float lo = i == 0 ? k - (array.get(hK, 1) - k) / 2 : (k + array.get(hK, i - 1)) / 2
            float hi = i == n - 1 ? k + (k - array.get(hK, n - 2)) / 2 : (k + array.get(hK, i + 1)) / 2
            float g = array.get(hG, i)
            float a = mx > 0 ? math.abs(g) / mx : 0.0
            color base = g >= 0 ? colHeatPos : colHeatNeg
            color c = color.from_gradient(a, 0.0, 1.0, color.new(base, 100), color.new(base, heatAlpha))
            array.push(hBx, box.new(xs, hi * conv, xl, lo * conv, xloc = xloc.bar_time, extend = extend.right, border_width = 0, bgcolor = c))

// ── ANNONCES MACRO DU JOUR ───────────────────────────────────────────────
var array<line>  evLn = array.new<line>()
var array<label> evLb = array.new<label>()
drawEvents() =>
    while array.size(evLn) > 0
        line.delete(array.pop(evLn))
    while array.size(evLb) > 0
        label.delete(array.pop(evLb))
    if showEvents and EV_DAY == str.format_time(timenow, "yyyy-MM-dd", "America/New_York")
        for [i, tt] in EV_TIME
            int hh = int(str.tonumber(str.substring(tt, 0, 2)))
            int mm = int(str.tonumber(str.substring(tt, 3, 5)))
            int ts = timestamp("America/New_York", year(timenow, "America/New_York"), month(timenow, "America/New_York"), dayofmonth(timenow, "America/New_York"), hh, mm)
            bool strong = array.get(EV_IMPACT, i) == "fort"
            color c = strong ? colSell : colPiv
            array.push(evLn, line.new(ts, close, ts, close * 1.0001, xloc = xloc.bar_time, extend = extend.both, color = color.new(c, 30), style = line.style_dotted, width = strong ? 2 : 1))
            array.push(evLb, label.new(ts, high, tt + " " + array.get(EV_TITLE, i), xloc = xloc.bar_time, yloc = yloc.abovebar, style = label.style_label_down, color = color.new(c, 20), textcolor = color.white, size = size.small))

drawGex() =>
    while array.size(gBx) > 0
        box.delete(array.pop(gBx))
    while array.size(gLn) > 0
        line.delete(array.pop(gLn))
    while array.size(gLb) > 0
        label.delete(array.pop(gLb))
    int xs = na(dayStart) ? time : dayStart
    int xl = time + 6 * timeframe.in_seconds() * 1000
    drawHeat(xs, xl)
    drawEvents()
    if showGex and mkt != "NONE" and not na(conv)
        gLine(gEmH * conv, "EM haut", colLv, line.style_dashed, xs, xl)
        gLine(gEmL * conv, "EM bas", colLv, line.style_dashed, xs, xl)
        gLine(gPiv * conv, "Pivot gamma", colPiv, line.style_dotted, xs, xl)
        gZone(gR2 * conv, "R2", sR2, colSell, xs, xl)
        gZone(gR1 * conv, "R1", sR1, colSell, xs, xl)
        gZone(gS1 * conv, "S1", sS1, colBuy, xs, xl)
        gZone(gS2 * conv, "S2", sS2, colBuy, xs, xl)

if barstate.islastconfirmedhistory or (justFrozen and barstate.isrealtime and barstate.isconfirmed)
    drawGex()

// ── CONTEXTE MACRO (informatif) ──────────────────────────────────────────
float vixD  = request.security("CBOE:VIX", "D", close[1], lookahead = barmerge.lookahead_on, ignore_invalid_symbol = true)
float vix3D = request.security("CBOE:VIX3M", "D", close[1], lookahead = barmerge.lookahead_on, ignore_invalid_symbol = true)

// ── TABLEAU ──────────────────────────────────────────────────────────────
var table tb = table.new(position.top_right, 2, 11, border_width = 1)
if barstate.islast and showTable
    color fg = chart.fg_color
    color bg = color.new(chart.bg_color, 8)
    string mktTxt = not isFut ? "signaux validés sur ES, MES, NQ, MNQ" : not tfB ? "unité de temps ≤ 1 h requise" : syminfo.ticker + (mkt == "NQ" ? " · Nasdaq 100" : " · S&P 500")
    string biasTxt = aBias > 0 ? "▲ HAUSSIER — achats seulement" : aBias < 0 ? (shortMode == "Toujours (plus de signaux, moins fiables)" or aTrend == -1 ? "▼ BAISSIER — ventes seulement" : "▼ baissier mais tendance 20 j haussière — pas de vente") : "neutre (en attente de Londres)"
    string stA = holiday ? "jour férié / séance écourtée : pas de signal" : not tfA ? "graphique ≤ 5 min requis" : mNY < 585 ? "range d'ouverture à 9h45, signal possible jusqu'à 11h30" : mNY < 690 and not aDecided ? "en attente de la cassure du range (≤ 11h30)" : aDecided ? "décidé pour aujourd'hui" : "fenêtre fermée (11h30)"
    string evTxt = ""
    if EV_DAY == str.format_time(timenow, "yyyy-MM-dd", "America/New_York")
        for [i, tt] in EV_TIME
            evTxt := evTxt + (evTxt == "" ? "" : " · ") + tt + " " + array.get(EV_TITLE, i)
    evTxt := evTxt == "" ? "aucune annonce majeure (ou couche du jour non recopiée)" : evTxt
    string vixTxt = na(vixD) ? "—" : "VIX " + str.tostring(vixD, "0.0") + (na(vix3D) ? "" : vixD > vix3D ? " · structure inversée (stress)" : " · structure normale")
    table.cell(tb, 0, 0, "ES/NQ PRO", text_color = fg, bgcolor = bg, text_size = size.normal)
    table.cell(tb, 1, 0, mktTxt, text_color = isFut and tfB ? fg : colSell, bgcolor = bg, text_size = size.small)
    table.cell(tb, 0, 1, "Biais de séance NY", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(tb, 1, 1, biasTxt + "  (Londres " + px(gLonL) + " – " + px(gLonH) + ")", text_color = aBias > 0 ? colBuy : aBias < 0 ? colSell : fg, bgcolor = bg, text_size = size.small)
    table.cell(tb, 0, 2, "Signal A", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(tb, 1, 2, stA + " · dernier : " + aTxt, text_color = fg, bgcolor = bg, text_size = size.small)
    table.cell(tb, 0, 3, "Tendance 20 j", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(tb, 1, 3, trendD == 1 ? "haussière (signal B : achats)" : trendD == -1 ? "baissière (signal B : ventes)" : "en calcul", text_color = trendD == 1 ? colBuy : trendD == -1 ? colSell : fg, bgcolor = bg, text_size = size.small)
    table.cell(tb, 0, 4, "Signal B", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(tb, 1, 4, (bPendSide != 0 ? "setup : cassure acceptée " + (bPendLv == dH ? "PDH" : "PDL") + " → signal si retest · " : "") + "dernier : " + bTxt, text_color = fg, bgcolor = bg, text_size = size.small)
    table.cell(tb, 0, 5, "Niveaux", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(tb, 1, 5, "veille " + px(dL) + " – " + px(dH) + " · Asie " + px(gAsL) + " – " + px(gAsH) + " · ouverture " + px(gOrL) + " – " + px(gOrH), text_color = fg, bgcolor = bg, text_size = size.small)
    table.cell(tb, 0, 6, "Annonces US", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(tb, 1, 6, evTxt, text_color = array.size(EV_TIME) > 0 ? colPiv : fg, bgcolor = bg, text_size = size.small)
    table.cell(tb, 0, 7, "Contexte", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(tb, 1, 7, vixTxt, text_color = fg, bgcolor = bg, text_size = size.small)
    table.cell(tb, 0, 8, "Backtest A", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(tb, 1, 8, mkt == "NQ" ? A_NQ_REF : A_ES_REF, text_color = fg, bgcolor = bg, text_size = size.small)
    table.cell(tb, 0, 9, "Backtest B", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(tb, 1, 9, mkt == "NQ" ? NQ_REF : ES_REF, text_color = fg, bgcolor = bg, text_size = size.small)
    table.cell(tb, 0, 10, "Sur ce graphique", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(tb, 1, 10, "A : " + str.tostring(aN) + " trades " + (aN > 0 ? rr(aSum) : "") + " · B : " + str.tostring(bN) + " trades " + (bN > 0 ? rr(bSum) : ""), text_color = fg, bgcolor = bg, text_size = size.small)

// ── ALERTES ──────────────────────────────────────────────────────────────
alertcondition(newABuy or newBBuy, "Signal d'ACHAT", "{{ticker}} : signal d'ACHAT ES/NQ Pro — voir entrée / stop / objectif sur le graphique")
alertcondition(newASell or newBSell, "Signal de VENTE", "{{ticker}} : signal de VENTE ES/NQ Pro — voir entrée / stop / objectif sur le graphique")
alertcondition(newA, "Signal A (cassure d'ouverture)", "{{ticker}} : signal A — cassure du range d'ouverture dans le sens de Londres")
alertcondition(newB, "Signal B (retest PDH/PDL)", "{{ticker}} : signal B — retest PDH/PDL dans la tendance")
'''


BACKTEST = ROOT / "backtest" / "results.json"


INTRADAY = ROOT / "backtest" / "intraday_results.json"


def stats_block():
    """Statistiques des backtests de référence -> constantes Pine + commentaire."""
    ref = {"A_ES": "backtest indisponible", "A_NQ": "backtest indisponible",
           "ES": "backtest indisponible", "NQ": "backtest indisponible"}
    comment = []
    if INTRADAY.exists():
        res = json.loads(INTRADAY.read_text())
        for m in ("ES", "NQ"):
            mk = res["markets"].get(m)
            if not mk:
                continue
            s = mk["summary"]
            pos = sum(1 for v in mk["by_year"].values() if v.get("totR", 0) > 0)
            ref["A_" + m] = (f"{s['n']} trades 2020-26 · {s['win']:.0f} % gagnants · PF {s['PF']} · "
                             f"{s['avgR']:+.2f} R/trade · {pos}/{len(mk['by_year'])} ans positifs")
            comment.append(f"//   Signal A {m} : {ref['A_' + m]}, pire série {s['dd']} R")
    if BACKTEST.exists():
        res = json.loads(BACKTEST.read_text())
        for m in ("ES", "NQ"):
            mk = res["markets"].get(m)
            if not mk or not mk["summary"].get("n"):
                continue
            s = mk["summary"]
            ref[m] = (f"{s['n']} signaux 2 ans · {s['win_rate']:.0f} % gagnants · PF {s['profit_factor']} · "
                      f"{s['expectancy_r']:+.2f} R/trade")
            comment.append(f"//   Signal B {m} : {ref[m]}, pire série {s['max_drawdown_r']} R")
    consts = "\n".join(f'{k}_REF = "{v}"' for k, v in ref.items())
    return consts, "\n".join(comment) or "//   (backtests non encore exécutés)"


def build() -> Path:
    blocks, summaries, days = [], [], []
    for sym in DATASETS:
        lv = latest_levels(sym)
        block, summary = dataset_block(sym, lv)
        blocks.append(block)
        summaries.append(summary)
        if lv:
            days.append(lv["day"])
    day = max(days) if days else "—"
    consts, comment = stats_block()
    import macro_calendar
    evs = macro_calendar.events_for(day) if day != "—" else []
    q = lambda x: '"' + x.replace('"', "'") + '"'
    ev_block = "\n".join([
        f'EV_DAY = "{day}"',
        "var array<string> EV_TIME = " + (f"array.from({', '.join(q(e['time']) for e in evs)})" if evs else "array.new<string>()"),
        "var array<string> EV_TITLE = " + (f"array.from({', '.join(q(e['title']) for e in evs)})" if evs else "array.new<string>()"),
        "var array<string> EV_IMPACT = " + (f"array.from({', '.join(q(e['impact']) for e in evs)})" if evs else "array.new<string>()"),
    ])
    for s in summaries:
        s["events"] = evs
    pine = (PINE_TEMPLATE.replace("{day}", day).replace("{data}", "\n\n".join(blocks))
            .replace("{stats}", consts).replace("//{stats_comment}", comment).replace("{events}", ev_block))
    OUT.mkdir(parents=True, exist_ok=True)
    PINE_FILE.write_text(pine, encoding="utf-8")
    (OUT / "levels.json").write_text(
        json.dumps({"day": day, "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "pine_file": PINE_FILE.name, "datasets": summaries}, indent=1),
        encoding="utf-8",
    )
    print(f"Indicateur TradingView régénéré : {PINE_FILE.relative_to(ROOT)} (plan GEX du {day})")
    return PINE_FILE


if __name__ == "__main__":
    build()
