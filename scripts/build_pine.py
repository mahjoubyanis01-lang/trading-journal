#!/usr/bin/env python3
"""Génère l'indicateur TradingView (Pine Script v6) des NIVEAUX CLÉS DU JOUR.

Les niveaux viennent de data/levels/<SYM>/<jour>.json : ils sont figés par le
premier snapshot CBOE de la journée (pré-marché) et ne changent plus ensuite.
L'indicateur est donc identique toute la séance ; il n'est régénéré qu'au
verrouillage des niveaux du jour suivant.

TradingView interdit tout appel réseau depuis Pine : les niveaux sont embarqués
dans le code. La conversion indice -> futures (ES/MES, NQ/MNQ) utilise la base
de clôture de la veille, figée pour toute la séance.

Sorties : tradingview/GEX_Levels_ES_NQ.pine
          tradingview/levels.json   (résumé lisible par la page web)
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


def pine_float(v) -> str:
    if v is None:
        return "float(na)"
    s = repr(round(float(v), 4))
    return s if ("." in s or "e" in s) else s + ".0"


def expected_move(lv: dict):
    n0 = lv.get("nearest_expiry") or {}
    if n0.get("em_up") is not None:
        return n0["em_up"], n0["em_down"], "straddle 0DTE"
    if lv.get("em_iv"):
        return lv["spot"] + lv["em_iv"], lv["spot"] - lv["em_iv"], "IV 30 j"
    return None, None, "—"


def dataset_block(sym: str, lv) -> tuple[str, dict]:
    if lv is None:
        vals = dict(DAY='""', LOCK='""', SPOT="float(na)", CW="float(na)", PW="float(na)",
                    FLIP="float(na)", C0="float(na)", P0="float(na)", EMU="float(na)",
                    EMD="float(na)", NET="float(na)", EXP0='"—"', EMSRC='"—"')
        ks = gs = None
        summary = {"symbol": sym, "available": False}
    else:
        n0 = lv.get("nearest_expiry") or {}
        em_up, em_down, em_src = expected_move(lv)
        vals = dict(
            DAY=f'"{lv["day"]}"',
            LOCK=f'"{lv["locked_at"][11:16]}"',
            SPOT=pine_float(lv["spot"]),
            CW=pine_float(lv.get("call_wall")),
            PW=pine_float(lv.get("put_wall")),
            FLIP=pine_float(lv.get("flip")),
            C0=pine_float(n0.get("call_wall")),
            P0=pine_float(n0.get("put_wall")),
            EMU=pine_float(em_up),
            EMD=pine_float(em_down),
            NET=pine_float(lv.get("net_gex")),
            EXP0=f'"{n0.get("expiration", "—")}"',
            EMSRC=f'"{em_src}"',
        )
        ks = ", ".join(pine_float(x["strike"]) for x in lv["key_strikes"])
        gs = ", ".join(pine_float(x["net_gex"]) for x in lv["key_strikes"])
        summary = {
            "symbol": sym, "available": True, "day": lv["day"], "locked_at": lv["locked_at"],
            "spot": lv["spot"], "call_wall": lv.get("call_wall"), "put_wall": lv.get("put_wall"),
            "flip": lv.get("flip"), "net_gex": lv.get("net_gex"),
            "zero_dte_call_wall": n0.get("call_wall"), "zero_dte_put_wall": n0.get("put_wall"),
            "zero_dte_expiration": n0.get("expiration"),
            "em_up": em_up, "em_down": em_down, "em_source": em_src,
            "key_strikes": lv["key_strikes"],
        }
    lines = [f"{sym}_{k:<5} = {v}" for k, v in vals.items()]
    lines.append(f"var array<float> {sym}_K = " + (f"array.from({ks})" if ks else "array.new<float>()"))
    lines.append(f"var array<float> {sym}_G = " + (f"array.from({gs})" if gs else "array.new<float>()"))
    return "\n".join(lines), summary


PINE_TEMPLATE = r'''//@version=6
// ════════════════════════════════════════════════════════════════════════
//  GEX Key Levels ES / NQ — niveaux clés FIXES de la journée (options CBOE)
//  Détection automatique : ES, MES -> S&P 500 (SPX) · NQ, MNQ -> Nasdaq 100 (NDX)
//
//  Niveaux du {day}, figés au premier snapshot de la journée et inchangés
//  jusqu'à la clôture : call wall, put wall, gamma flip, murs 0DTE,
//  expected move du jour, strikes GEX majeurs.
//  Conversion indice -> futures : base de clôture de la veille, figée pour
//  toute la séance (les lignes ne bougent pas pendant la journée).
//
//  Niveaux du jour suivant : https://mahjoubyanis01-lang.github.io/trading-journal/tradingview.html
//  (disponibles chaque matin dès 8h30 New York / 14h30 Paris)
// ════════════════════════════════════════════════════════════════════════
indicator("GEX Key Levels ES/NQ (CBOE)", shorttitle = "GEX Levels", overlay = true, max_lines_count = 60, max_labels_count = 60)

// ── NIVEAUX DU JOUR (générés automatiquement — ne pas modifier) ──────────
{data}

// ── PARAMÈTRES ───────────────────────────────────────────────────────────
srcMode   = input.string("Indice (SPX / NDX)", "Source des options", options = ["Indice (SPX / NDX)", "ETF (SPY / QQQ)"])
mktMode   = input.string("Auto", "Marché", options = ["Auto", "S&P 500", "Nasdaq 100"])
showTop   = input.int(5, "Strikes GEX majeurs", minval = 0, maxval = 10)
show0dte  = input.bool(true, "Murs 0DTE")
showEM    = input.bool(true, "Expected move du jour")
showTable = input.bool(true, "Tableau")
colPos    = input.color(#2a78d6, "Call wall / GEX positif")
colNeg    = input.color(#e34948, "Put wall / GEX négatif")
colFlip   = input.color(#eda100, "Gamma flip")
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
pickS(string k, string a, string b, string c, string d) => k == "SPX" ? a : k == "SPY" ? b : k == "NDX" ? c : d
pickA(string k, array<float> a, array<float> b, array<float> c, array<float> d) => k == "SPX" ? a : k == "SPY" ? b : k == "NDX" ? c : d

string dDay   = pickS(srcName, SPX_DAY, SPY_DAY, NDX_DAY, QQQ_DAY)
string dLock  = pickS(srcName, SPX_LOCK, SPY_LOCK, NDX_LOCK, QQQ_LOCK)
string d0Exp  = pickS(srcName, SPX_EXP0, SPY_EXP0, NDX_EXP0, QQQ_EXP0)
string dEmSrc = pickS(srcName, SPX_EMSRC, SPY_EMSRC, NDX_EMSRC, QQQ_EMSRC)
float dSpot = pickF(srcName, SPX_SPOT, SPY_SPOT, NDX_SPOT, QQQ_SPOT)
float dCW   = pickF(srcName, SPX_CW, SPY_CW, NDX_CW, QQQ_CW)
float dPW   = pickF(srcName, SPX_PW, SPY_PW, NDX_PW, QQQ_PW)
float dFlip = pickF(srcName, SPX_FLIP, SPY_FLIP, NDX_FLIP, QQQ_FLIP)
float d0CW  = pickF(srcName, SPX_C0, SPY_C0, NDX_C0, QQQ_C0)
float d0PW  = pickF(srcName, SPX_P0, SPY_P0, NDX_P0, QQQ_P0)
float dEmU  = pickF(srcName, SPX_EMU, SPY_EMU, NDX_EMU, QQQ_EMU)
float dEmD  = pickF(srcName, SPX_EMD, SPY_EMD, NDX_EMD, QQQ_EMD)
float dNet  = pickF(srcName, SPX_NET, SPY_NET, NDX_NET, QQQ_NET)
array<float> dK = pickA(srcName, SPX_K, SPY_K, NDX_K, QQQ_K)
array<float> dG = pickA(srcName, SPX_G, SPY_G, NDX_G, QQQ_G)

// ── BASE FIGÉE POUR LA SÉANCE ───────────────────────────────────────────
// ratio = prix du graphique / indice source. On retient la dernière valeur
// observée pendant la séance cash précédente (clôture) et on la fige à
// l'ouverture de la nouvelle séance : les niveaux convertis ne bougent plus.
bool chartIsSrc = tk == srcName
float idxMain = request.security(srcTv, timeframe.period, close, gaps = barmerge.gaps_on, ignore_invalid_symbol = true)
float idxAlt  = request.security(altTv, timeframe.period, close, gaps = barmerge.gaps_on, ignore_invalid_symbol = true)
float idx = na(idxMain) ? idxAlt : idxMain
var float lastRatio = na
var float dayRatio  = na
var int   dayStart  = na
float prevRatio = lastRatio
if session.isfirstbar
    dayStart := time
    if not na(prevRatio)
        dayRatio := prevRatio
if not na(idx) and idx > 0
    lastRatio := close / idx
if na(dayRatio) and not na(lastRatio)
    dayRatio := lastRatio
bool approx = not chartIsSrc and na(dayRatio)
float conv = chartIsSrc ? 1.0 : not na(dayRatio) ? dayRatio : (na(dSpot) ? na : close / dSpot)

float flipY = dFlip * conv
float cwY   = dCW * conv
float pwY   = dPW * conv
float emUY  = dEmU * conv
float emDY  = dEmD * conv

fmtG(float v) =>
    na(v) ? "—" : math.abs(v) >= 1000 ? (v >= 0 ? "+" : "") + str.tostring(v / 1000, "#.#") + " Md$" : (v >= 0 ? "+" : "") + str.tostring(v, "#") + " M$"

// ── DESSIN (lignes ancrées sur l'ouverture de la séance) ─────────────────
var array<line>  lns = array.new<line>()
var array<label> lbs = array.new<label>()

drawLevel(float y, float srcLvl, string name, color col, int w, string sty) =>
    if not na(y)
        int x1 = na(dayStart) ? time : dayStart
        array.push(lns, line.new(x1, y, time, y, xloc = xloc.bar_time, extend = extend.right, color = col, width = w, style = sty))
        string txt = name + "  " + str.tostring(math.round_to_mintick(y)) + (chartIsSrc ? "" : "  (" + srcName + " " + str.tostring(srcLvl, "#.##") + ")")
        array.push(lbs, label.new(bar_index + 3, y, txt, style = label.style_label_left, color = color.new(col, 82), textcolor = col, size = size.small))

if barstate.islast
    while array.size(lns) > 0
        line.delete(array.pop(lns))
    while array.size(lbs) > 0
        label.delete(array.pop(lbs))
    if mkt != "NONE" and not na(conv)
        float maxAbs = 0.0
        for g in dG
            maxAbs := math.max(maxAbs, math.abs(g))
        int n = 0
        for [i, k] in dK
            if n < showTop and (na(dCW) or k != dCW) and (na(dPW) or k != dPW)
                float g = array.get(dG, i)
                int w = 1 + int(math.round(2 * math.abs(g) / math.max(maxAbs, 1e-9)))
                drawLevel(k * conv, k, "GEX " + fmtG(g), color.new(g >= 0 ? colPos : colNeg, 45), w, line.style_solid)
                n += 1
        if showEM
            drawLevel(emUY, dEmU, "EXPECTED MOVE ▲", colEM, 2, line.style_dashed)
            drawLevel(emDY, dEmD, "EXPECTED MOVE ▼", colEM, 2, line.style_dashed)
        if show0dte
            drawLevel(d0CW * conv, d0CW, "0DTE call wall", colPos, 1, line.style_dotted)
            drawLevel(d0PW * conv, d0PW, "0DTE put wall", colNeg, 1, line.style_dotted)
        drawLevel(flipY, dFlip, "GAMMA FLIP", colFlip, 2, line.style_dashed)
        drawLevel(pwY, dPW, "PUT WALL", colNeg, 3, line.style_solid)
        drawLevel(cwY, dCW, "CALL WALL", colPos, 3, line.style_solid)

// ── TABLEAU ─────────────────────────────────────────────────────────────
var table info = table.new(position.top_right, 2, 6, border_width = 1)
if barstate.islast and showTable
    color fg = chart.fg_color
    color bg = color.new(chart.bg_color, 10)
    bool isToday = dDay == str.format_time(timenow, "yyyy-MM-dd", "America/New_York")
    string dayTxt = dDay == "" ? "aucune donnée" : str.substring(dDay, 8, 10) + "/" + str.substring(dDay, 5, 7) + " · figés à " + dLock + " NY"
    string statusTxt = dDay == "" ? "—" : isToday ? "✓ niveaux du jour" : "niveaux de la dernière séance — ceux du jour dès 8h30 NY"
    color statusCol = isToday ? color.new(#0ca30c, 0) : colFlip
    bool posGamma = not na(dNet) and dNet >= 0
    table.cell(info, 0, 0, "GEX Key Levels", text_color = fg, bgcolor = bg, text_size = size.small)
    table.cell(info, 1, 0, mkt == "NONE" ? "marché non reconnu" : syminfo.ticker + " → " + srcName, text_color = mkt == "NONE" ? colNeg : fg, bgcolor = bg, text_size = size.small)
    table.cell(info, 0, 1, "Niveaux du", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(info, 1, 1, dayTxt, text_color = fg, bgcolor = bg, text_size = size.small)
    table.cell(info, 0, 2, "Statut", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(info, 1, 2, statusTxt, text_color = statusCol, bgcolor = bg, text_size = size.small)
    table.cell(info, 0, 3, "Régime", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(info, 1, 3, na(dNet) ? "—" : (posGamma ? "Gamma + (marché amorti) " : "Gamma − (marché volatil) ") + fmtG(dNet), text_color = posGamma ? colPos : colNeg, bgcolor = bg, text_size = size.small)
    table.cell(info, 0, 4, "Expected move", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(info, 1, 4, na(dEmU) or na(conv) ? "—" : "±" + str.tostring(math.round_to_mintick((emUY - emDY) / 2)) + " pts (" + dEmSrc + ")", text_color = fg, bgcolor = bg, text_size = size.small)
    table.cell(info, 0, 5, "Base", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(info, 1, 5, chartIsSrc ? "graphique = source" : approx ? "approximative (indice indisponible)" : "figée ×" + str.tostring(conv, "#.####") + " (clôture veille)", text_color = approx ? colNeg : fg, bgcolor = bg, text_size = size.small)

// ── ALERTES ─────────────────────────────────────────────────────────────
alertcondition(ta.cross(close, flipY), "Croisement du gamma flip", "{{ticker}} croise le gamma flip GEX du jour")
alertcondition(ta.crossover(high, cwY), "Test du call wall", "{{ticker}} atteint le call wall GEX du jour")
alertcondition(ta.crossunder(low, pwY), "Test du put wall", "{{ticker}} atteint le put wall GEX du jour")
alertcondition(ta.crossover(high, emUY) or ta.crossunder(low, emDY), "Sortie de l'expected move", "{{ticker}} sort de l'expected move du jour")
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
    print(f"Indicateur TradingView régénéré : {PINE_FILE.relative_to(ROOT)} (niveaux du {day})")
    return PINE_FILE


if __name__ == "__main__":
    build()
