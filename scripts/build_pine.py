#!/usr/bin/env python3
"""Génère l'indicateur TradingView (Pine Script v6) « Plan du jour » :
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
    return "\n".join(lines), summary


PINE_TEMPLATE = r'''//@version=6
// ════════════════════════════════════════════════════════════════════════
//  PLAN DU JOUR ES / NQ — points de retournement potentiels (options CBOE)
//  Plan du {day} · détection automatique : ES, MES -> SPX · NQ, MNQ -> NDX
//
//  R1/R2 : résistances · S1/S2 : supports — strikes où le gamma des options
//  est le plus concentré à portée de la séance (les dealers y couvrent le
//  plus : le prix a tendance à y buter ou y rebondir). ★ = force du niveau.
//  Pivot gamma : au-dessus, marché plutôt amorti ; en dessous, plus nerveux.
//  Expected move : bornes du mouvement attendu par le marché des options.
//
//  Le plan est calculé une fois par jour et DESSINÉ UNE SEULE FOIS : il ne
//  bouge pas pendant la séance (base futures/indice de la veille, figée).
//  Plan du jour suivant (dès 8h30 New York / 14h30 Paris) :
//  https://mahjoubyanis01-lang.github.io/trading-journal/tradingview.html
// ════════════════════════════════════════════════════════════════════════
indicator("Plan du jour ES/NQ — retournements GEX", shorttitle = "Plan GEX", overlay = true, max_lines_count = 40, max_labels_count = 40, max_boxes_count = 40)

// ── PLAN DU JOUR (généré automatiquement — ne pas modifier) ──────────────
{data}

// ── PARAMÈTRES ───────────────────────────────────────────────────────────
mktMode   = input.string("Auto", "Marché", options = ["Auto", "S&P 500", "Nasdaq 100"])
srcMode   = input.string("Indice (SPX / NDX)", "Source des options", options = ["Indice (SPX / NDX)", "ETF (SPY / QQQ)"])
showEM    = input.bool(true, "Expected move (bornes du jour)")
showPiv   = input.bool(true, "Pivot gamma")
showTable = input.bool(true, "Tableau du plan")
zonePct   = input.float(0.04, "Épaisseur des zones (% du prix)", minval = 0.0, maxval = 0.5, step = 0.01)
colRes    = input.color(#e34948, "Résistances")
colSup    = input.color(#0ca30c, "Supports")
colPiv    = input.color(#eda100, "Pivot gamma")
colEM     = input.color(#9085e9, "Expected move")

// ── DÉTECTION DU MARCHÉ ─────────────────────────────────────────────────
string root = syminfo.root
string tk   = syminfo.ticker
bool isSP = root == "ES" or root == "MES" or tk == "SPX" or tk == "SPY" or str.contains(tk, "US500") or str.contains(tk, "SPX500") or str.contains(tk, "SP500")
bool isNQ = root == "NQ" or root == "MNQ" or tk == "NDX" or tk == "QQQ" or str.contains(tk, "NAS100") or str.contains(tk, "US100") or str.contains(tk, "NDX100") or str.contains(tk, "USTEC")
string mkt = mktMode == "S&P 500" ? "SP" : mktMode == "Nasdaq 100" ? "NQ" : isSP ? "SP" : isNQ ? "NQ" : "NONE"
bool useEtf = srcMode == "ETF (SPY / QQQ)"
string srcName = mkt == "NQ" ? (useEtf ? "QQQ" : "NDX") : (useEtf ? "SPY" : "SPX")
string srcTv   = mkt == "NQ" ? (useEtf ? "NASDAQ:QQQ" : "NASDAQ:NDX") : (useEtf ? "AMEX:SPY" : "SP:SPX")
string altTv   = mkt == "NQ" ? (useEtf ? "NASDAQ:QQQ" : "TVC:NDX") : (useEtf ? "AMEX:SPY" : "TVC:SPX")

pickF(string k, float a, float b, float c, float d) => k == "SPX" ? a : k == "SPY" ? b : k == "NDX" ? c : d
pickI(string k, int a, int b, int c, int d) => k == "SPX" ? a : k == "SPY" ? b : k == "NDX" ? c : d
pickS(string k, string a, string b, string c, string d) => k == "SPX" ? a : k == "SPY" ? b : k == "NDX" ? c : d

string dDay  = pickS(srcName, SPX_DAY, SPY_DAY, NDX_DAY, QQQ_DAY)
string dLock = pickS(srcName, SPX_LOCK, SPY_LOCK, NDX_LOCK, QQQ_LOCK)
string dEmSrc = pickS(srcName, SPX_EMSRC, SPY_EMSRC, NDX_EMSRC, QQQ_EMSRC)
float dNet = pickF(srcName, SPX_NET, SPY_NET, NDX_NET, QQQ_NET)
float dR2  = pickF(srcName, SPX_R2, SPY_R2, NDX_R2, QQQ_R2)
float dR1  = pickF(srcName, SPX_R1, SPY_R1, NDX_R1, QQQ_R1)
float dS1  = pickF(srcName, SPX_S1, SPY_S1, NDX_S1, QQQ_S1)
float dS2  = pickF(srcName, SPX_S2, SPY_S2, NDX_S2, QQQ_S2)
int   sR2  = pickI(srcName, SPX_R2S, SPY_R2S, NDX_R2S, QQQ_R2S)
int   sR1  = pickI(srcName, SPX_R1S, SPY_R1S, NDX_R1S, QQQ_R1S)
int   sS1  = pickI(srcName, SPX_S1S, SPY_S1S, NDX_S1S, QQQ_S1S)
int   sS2  = pickI(srcName, SPX_S2S, SPY_S2S, NDX_S2S, QQQ_S2S)
float dPiv = pickF(srcName, SPX_PIV, SPY_PIV, NDX_PIV, QQQ_PIV)
float dEmH = pickF(srcName, SPX_EMH, SPY_EMH, NDX_EMH, QQQ_EMH)
float dEmL = pickF(srcName, SPX_EML, SPY_EML, NDX_EML, QQQ_EML)

// ── BASE FUTURES / INDICE, GELÉE POUR LA SÉANCE ─────────────────────────
// L'écart futures/indice est mesuré en moyenne sur 9h30-9h45 New York puis
// gelé toute la journée (la clôture, faussée par l'enchère, n'est pas utilisée).
// Avant 9h45 : écart gelé de la séance précédente, marqué « provisoire ».
bool chartIsSrc = tk == srcName
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
if not chartIsSrc and not na(idx) and idx > 0
    string nyDay = str.format_time(time, "yyyy-MM-dd", "America/New_York")
    int hm = hour(time, "America/New_York") * 60 + minute(time, "America/New_York")
    if nyDay != accDay
        ratioPrev := frozen ? ratioFinal : accN > 0 ? accSum / accN : ratioPrev
        accDay := nyDay
        accSum := 0.0
        accN := 0
        frozen := false
        ratioFinal := na
    if not frozen
        if hm < 9 * 60 + 45 or accN == 0
            accSum += close / idx
            accN += 1
        if hm >= 9 * 60 + 45
            ratioFinal := accSum / accN
            frozen := true
            justFrozen := true
bool frozenToday = frozen and accDay == str.format_time(time, "yyyy-MM-dd", "America/New_York")
bool provisional = not chartIsSrc and not frozenToday
float conv = chartIsSrc ? 1.0 : frozen ? ratioFinal : not na(ratioPrev) ? ratioPrev : accN > 0 ? accSum / accN : na

float r2Y  = dR2 * conv
float r1Y  = dR1 * conv
float s1Y  = dS1 * conv
float s2Y  = dS2 * conv
float pivY = dPiv * conv
float emhY = dEmH * conv
float emlY = dEmL * conv

stars(int s) => s >= 3 ? "★★★" : s == 2 ? "★★" : s == 1 ? "★" : ""
px(float v) => na(v) ? "—" : str.tostring(math.round_to_mintick(v))

// ── DESSIN ──────────────────────────────────────────────────────────────
// Dessiné une fois sur la dernière barre confirmée, puis une seule autre
// fois quand l'écart du jour est gelé (9h45 NY). Jamais recalculé ensuite.
var array<box>   bxs = array.new<box>()
var array<line>  lns = array.new<line>()
var array<label> lbs = array.new<label>()
var table tb = table.new(position.top_right, 2, 8, border_width = 1)

zone(float y, string name, int s, color col, int xs, int xl) =>
    if not na(y)
        float h = y * zonePct / 100
        array.push(bxs, box.new(xs, y + h, xl, y - h, xloc = xloc.bar_time, extend = extend.right, border_color = color.new(col, 40), bgcolor = color.new(col, 88 - 6 * s)))
        array.push(lns, line.new(xs, y, xl, y, xloc = xloc.bar_time, extend = extend.right, color = col, width = math.max(1, s)))
        array.push(lbs, label.new(xl, y, name + " " + stars(s) + "   " + px(y), xloc = xloc.bar_time, style = label.style_label_left, color = color.new(col, 80), textcolor = col, size = size.normal))

level(float y, string name, color col, string sty, int xs, int xl) =>
    if not na(y)
        array.push(lns, line.new(xs, y, xl, y, xloc = xloc.bar_time, extend = extend.right, color = col, width = 2, style = sty))
        array.push(lbs, label.new(xl, y, name + "   " + px(y), xloc = xloc.bar_time, style = label.style_label_left, color = color.new(col, 85), textcolor = col, size = size.small))

drawPlan() =>
    while array.size(bxs) > 0
        box.delete(array.pop(bxs))
    while array.size(lns) > 0
        line.delete(array.pop(lns))
    while array.size(lbs) > 0
        label.delete(array.pop(lbs))
    table.clear(tb, 0, 0, 1, 7)
    color fg = chart.fg_color
    color bg = color.new(chart.bg_color, 8)
    if mkt == "NONE" or na(conv)
        table.cell(tb, 0, 0, mkt == "NONE" ? "Plan GEX : marché non reconnu — choisir S&P 500 ou Nasdaq 100 dans les paramètres" : "Plan GEX : cours de " + srcName + " indisponible pour convertir les niveaux", text_color = color.white, bgcolor = colRes, text_size = size.small)
    else
        int xs = na(dayStart) ? time : dayStart
        int xl = time + 6 * timeframe.in_seconds() * 1000
        if showEM
            level(emhY, "BORNE HAUTE (expected move)", colEM, line.style_dashed, xs, xl)
            level(emlY, "BORNE BASSE (expected move)", colEM, line.style_dashed, xs, xl)
        if showPiv
            level(pivY, "PIVOT GAMMA", colPiv, line.style_dotted, xs, xl)
        zone(r2Y, "R2", sR2, colRes, xs, xl)
        zone(r1Y, "R1", sR1, colRes, xs, xl)
        zone(s1Y, "S1", sS1, colSup, xs, xl)
        zone(s2Y, "S2", sS2, colSup, xs, xl)
        if showTable
            bool isToday = dDay == str.format_time(timenow, "yyyy-MM-dd", "America/New_York")
            string dd = dDay == "" ? "—" : str.substring(dDay, 8, 10) + "/" + str.substring(dDay, 5, 7)
            bool posGamma = not na(dNet) and dNet >= 0
            table.cell(tb, 0, 0, "PLAN DU " + dd, text_color = fg, bgcolor = bg, text_size = size.normal)
            table.cell(tb, 1, 0, syminfo.ticker + " → " + srcName + " · plan figé " + dLock + " NY", text_color = fg, bgcolor = bg, text_size = size.small)
            table.cell(tb, 0, 1, "Statut", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
            table.cell(tb, 1, 1, isToday ? "✓ plan du jour" : "plan de la séance précédente (nouveau dès 8h30 NY)", text_color = isToday ? colSup : colPiv, bgcolor = bg, text_size = size.small)
            table.cell(tb, 0, 2, "Résistances", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
            table.cell(tb, 1, 2, "R1 " + px(r1Y) + " " + stars(sR1) + "   R2 " + px(r2Y) + " " + stars(sR2), text_color = colRes, bgcolor = bg, text_size = size.small)
            table.cell(tb, 0, 3, "Supports", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
            table.cell(tb, 1, 3, "S1 " + px(s1Y) + " " + stars(sS1) + "   S2 " + px(s2Y) + " " + stars(sS2), text_color = colSup, bgcolor = bg, text_size = size.small)
            table.cell(tb, 0, 4, "Expected move", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
            table.cell(tb, 1, 4, px(emlY) + " – " + px(emhY) + " (" + dEmSrc + ")", text_color = colEM, bgcolor = bg, text_size = size.small)
            table.cell(tb, 0, 5, "Pivot gamma", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
            table.cell(tb, 1, 5, px(pivY), text_color = colPiv, bgcolor = bg, text_size = size.small)
            table.cell(tb, 0, 6, "Régime", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
            table.cell(tb, 1, 6, na(dNet) ? "—" : posGamma ? "Gamma + : rebonds sur niveaux, range" : "Gamma − : mouvements amplifiés, cassures", text_color = fg, bgcolor = bg, text_size = size.small)
            table.cell(tb, 0, 7, "Écart " + srcName, text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
            table.cell(tb, 1, 7, chartIsSrc ? "graphique = source" : provisional ? "provisoire (veille) — gelé à 9h45 NY" : "gelé à 9h45 NY ×" + str.tostring(conv, "#.#####"), text_color = provisional ? colPiv : fg, bgcolor = bg, text_size = size.small)

if barstate.islastconfirmedhistory or (justFrozen and barstate.isrealtime and barstate.isconfirmed)
    drawPlan()

// ── ALERTES ─────────────────────────────────────────────────────────────
alertcondition(ta.crossover(high, r1Y) or ta.crossover(high, r2Y), "Test d'une résistance (R1/R2)", "{{ticker}} teste une résistance du plan GEX")
alertcondition(ta.crossunder(low, s1Y) or ta.crossunder(low, s2Y), "Test d'un support (S1/S2)", "{{ticker}} teste un support du plan GEX")
alertcondition(ta.cross(close, pivY), "Croisement du pivot gamma", "{{ticker}} croise le pivot gamma")
alertcondition(ta.crossover(high, emhY) or ta.crossunder(low, emlY), "Sortie de l'expected move", "{{ticker}} sort de l'expected move du jour")
'''


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
    pine = PINE_TEMPLATE.replace("{day}", day).replace("{data}", "\n\n".join(blocks))
    OUT.mkdir(parents=True, exist_ok=True)
    PINE_FILE.write_text(pine, encoding="utf-8")
    (OUT / "levels.json").write_text(
        json.dumps({"day": day, "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "pine_file": PINE_FILE.name, "datasets": summaries}, indent=1),
        encoding="utf-8",
    )
    print(f"Plan du jour TradingView régénéré : {PINE_FILE.relative_to(ROOT)} ({day})")
    return PINE_FILE


if __name__ == "__main__":
    build()
