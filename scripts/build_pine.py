#!/usr/bin/env python3
"""Génère l'indicateur TradingView (Pine Script v6) à partir des derniers
snapshots CBOE de data/options/.

TradingView interdit tout appel réseau depuis un script Pine : les niveaux sont
donc embarqués dans le code, régénéré automatiquement après chaque snapshot
(toutes les 30 min en séance). La conversion des niveaux indice -> futures
(ES/MES, NQ/MNQ) se fait elle en temps réel dans TradingView.

Sorties : tradingview/GEX_Levels_ES_NQ.pine
          tradingview/levels.json   (résumé lisible par la page web)
Usage   : python3 scripts/build_pine.py
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "options"
OUT = ROOT / "tradingview"
PINE_FILE = OUT / "GEX_Levels_ES_NQ.pine"
TOP_N = 15
DATASETS = ["SPX", "SPY", "NDX", "QQQ"]


def latest_snapshot(sym: str):
    days_file = DATA / sym / "days.json"
    if not days_file.exists():
        return None
    days = json.loads(days_file.read_text())["days"]
    for day in reversed(days):
        idx_file = DATA / sym / day / "day.json"
        if not idx_file.exists():
            continue
        snaps = json.loads(idx_file.read_text())["snapshots"]
        if snaps:
            return json.loads((DATA / sym / day / snaps[-1]["file"]).read_text())
    return None


def pine_float(v) -> str:
    if v is None:
        return "float(na)"
    s = repr(round(float(v), 4))
    return s if ("." in s or "e" in s) else s + ".0"


def dataset_block(sym: str, snap) -> tuple[str, dict]:
    if snap is None:
        lines = [
            f"{sym}_TS    = 0",
            f"{sym}_SPOT  = float(na)",
            f"{sym}_FLIP  = float(na)",
            f"{sym}_CW    = float(na)",
            f"{sym}_PW    = float(na)",
            f"{sym}_0CW   = float(na)",
            f"{sym}_0PW   = float(na)",
            f"{sym}_NET   = float(na)",
            f'{sym}_0EXP  = "—"',
            f"var array<float> {sym}_K = array.new<float>()",
            f"var array<float> {sym}_G = array.new<float>()",
        ]
        return "\n".join(lines), {"symbol": sym, "available": False}

    s = snap["summary"]
    n0 = snap.get("nearest_expiry") or {}
    ts_ms = int(datetime.fromisoformat(snap["captured"]).timestamp() * 1000)
    nets = [
        (k, c + p)
        for k, c, p in zip(snap["strikes"], snap["call_gex"], snap["put_gex"])
    ]
    top = sorted(nets, key=lambda kv: abs(kv[1]), reverse=True)[:TOP_N]
    ks = ", ".join(pine_float(k) for k, _ in top) or ""
    gs = ", ".join(pine_float(g) for _, g in top) or ""
    lines = [
        f"{sym}_TS    = {ts_ms}  // {snap['captured']}",
        f"{sym}_SPOT  = {pine_float(snap['spot'])}",
        f"{sym}_FLIP  = {pine_float(s.get('flip'))}",
        f"{sym}_CW    = {pine_float(s.get('call_wall'))}",
        f"{sym}_PW    = {pine_float(s.get('put_wall'))}",
        f"{sym}_0CW   = {pine_float(n0.get('call_wall'))}",
        f"{sym}_0PW   = {pine_float(n0.get('put_wall'))}",
        f"{sym}_NET   = {pine_float(s.get('net_gex'))}",
        f'{sym}_0EXP  = "{n0.get("expiration", "—")}"',
        f"var array<float> {sym}_K = array.from({ks})" if top else f"var array<float> {sym}_K = array.new<float>()",
        f"var array<float> {sym}_G = array.from({gs})" if top else f"var array<float> {sym}_G = array.new<float>()",
    ]
    summary = {
        "symbol": sym,
        "available": True,
        "captured": snap["captured"],
        "spot": snap["spot"],
        "net_gex": s.get("net_gex"),
        "flip": s.get("flip"),
        "call_wall": s.get("call_wall"),
        "put_wall": s.get("put_wall"),
        "nearest_expiry": n0 or None,
        "top_strikes": [{"strike": k, "net_gex": round(g, 1)} for k, g in top],
    }
    return "\n".join(lines), summary


PINE_TEMPLATE = r'''//@version=6
// ════════════════════════════════════════════════════════════════════════
//  GEX Levels ES / NQ — niveaux de gamma exposure CBOE pour futures mini/micro
//  Détection automatique : ES, MES (S&P 500) · NQ, MNQ (Nasdaq 100)
//  + SPX, SPY, NDX, QQQ et CFD US500 / NAS100.
//
//  Données : chaînes d'options CBOE, snapshot du {generated}.
//  Ce fichier est régénéré automatiquement après chaque snapshot (toutes les
//  30 min en séance US) : https://mahjoubyanis01-lang.github.io/trading-journal/tradingview.html
//  TradingView n'autorise aucun accès internet depuis Pine : pour rafraîchir,
//  recopiez la dernière version (bouton « Copier » de la page ci-dessus).
//  La conversion indice -> futures (base ES/SPX, NQ/NDX) est, elle, calculée
//  en temps réel par TradingView.
// ════════════════════════════════════════════════════════════════════════
indicator("GEX Levels ES/NQ (CBOE)", shorttitle = "GEX ES/NQ", overlay = true, max_lines_count = 100, max_labels_count = 100)

// ── DONNÉES (générées automatiquement — ne pas modifier) ─────────────────
GENERATED = "{generated}"
{data}

// ── PARAMÈTRES ───────────────────────────────────────────────────────────
srcMode    = input.string("Indice (SPX / NDX)", "Source des options", options = ["Indice (SPX / NDX)", "ETF (SPY / QQQ)"])
mktMode    = input.string("Auto", "Marché", options = ["Auto", "S&P 500", "Nasdaq 100"])
showTop    = input.int(8, "Strikes GEX majeurs affichés", minval = 0, maxval = 15)
show0dte   = input.bool(true, "Murs de l'échéance la plus proche (0DTE)")
showTable  = input.bool(true, "Tableau d'informations")
lineLen    = input.int(150, "Longueur des lignes vers la gauche (barres)", minval = 5, maxval = 4000)
colPos     = input.color(#2a78d6, "Call wall / GEX positif")
colNeg     = input.color(#e34948, "Put wall / GEX négatif")
colFlip    = input.color(#eda100, "Gamma flip")

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
pickA(string k, array<float> a, array<float> b, array<float> c, array<float> d) => k == "SPX" ? a : k == "SPY" ? b : k == "NDX" ? c : d

int   dTs   = pickI(srcName, SPX_TS, SPY_TS, NDX_TS, QQQ_TS)
float dSpot = pickF(srcName, SPX_SPOT, SPY_SPOT, NDX_SPOT, QQQ_SPOT)
float dFlip = pickF(srcName, SPX_FLIP, SPY_FLIP, NDX_FLIP, QQQ_FLIP)
float dCW   = pickF(srcName, SPX_CW, SPY_CW, NDX_CW, QQQ_CW)
float dPW   = pickF(srcName, SPX_PW, SPY_PW, NDX_PW, QQQ_PW)
float d0CW  = pickF(srcName, SPX_0CW, SPY_0CW, NDX_0CW, QQQ_0CW)
float d0PW  = pickF(srcName, SPX_0PW, SPY_0PW, NDX_0PW, QQQ_0PW)
float dNet  = pickF(srcName, SPX_NET, SPY_NET, NDX_NET, QQQ_NET)
string d0Exp = pickS(srcName, SPX_0EXP, SPY_0EXP, NDX_0EXP, QQQ_0EXP)
array<float> dK = pickA(srcName, SPX_K, SPY_K, NDX_K, QQQ_K)
array<float> dG = pickA(srcName, SPX_G, SPY_G, NDX_G, QQQ_G)

// ── CONVERSION TEMPS RÉEL INDICE -> INSTRUMENT DU GRAPHIQUE ─────────────
// ratio = prix du graphique / prix de l'indice source, mis à jour à chaque
// barre où l'indice cote (base futures live), conservé hors séance.
bool chartIsSrc = tk == srcName
float idxMain = request.security(srcTv, timeframe.period, close, gaps = barmerge.gaps_on, ignore_invalid_symbol = true)
float idxAlt  = request.security(altTv, timeframe.period, close, gaps = barmerge.gaps_on, ignore_invalid_symbol = true)
float idx = na(idxMain) ? idxAlt : idxMain
var float ratio = na
if chartIsSrc
    ratio := 1.0
else if not na(idx) and idx > 0
    ratio := close / idx
bool liveBasis = not na(ratio)
float conv = liveBasis ? ratio : (na(dSpot) ? na : close / dSpot)

// ── NIVEAUX CONVERTIS (séries, utilisables pour les alertes) ────────────
float flipY = dFlip * conv
float cwY   = dCW * conv
float pwY   = dPW * conv

fmtG(float v) =>
    na(v) ? "—" : math.abs(v) >= 1000 ? (v >= 0 ? "+" : "") + str.tostring(v / 1000, "#.#") + " Md$" : (v >= 0 ? "+" : "") + str.tostring(v, "#") + " M$"

// ── DESSIN ──────────────────────────────────────────────────────────────
var array<line>  lns = array.new<line>()
var array<label> lbs = array.new<label>()

drawLevel(float y, float srcLvl, string name, color col, int w, string sty, bool same) =>
    if not na(y)
        int x1 = math.max(0, bar_index - lineLen)
        array.push(lns, line.new(x1, y, bar_index, y, extend = extend.right, color = col, width = w, style = sty))
        string txt = name + "  " + str.tostring(math.round_to_mintick(y)) + (same ? "" : "  (" + srcName + " " + str.tostring(srcLvl, "#.##") + ")")
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
                color c = g >= 0 ? color.new(colPos, 45) : color.new(colNeg, 45)
                drawLevel(k * conv, k, "GEX " + fmtG(g), c, w, line.style_solid, chartIsSrc)
                n += 1
        if show0dte
            drawLevel(d0CW * conv, d0CW, "0DTE call wall", colPos, 1, line.style_dotted, chartIsSrc)
            drawLevel(d0PW * conv, d0PW, "0DTE put wall", colNeg, 1, line.style_dotted, chartIsSrc)
        drawLevel(flipY, dFlip, "Gamma flip", colFlip, 2, line.style_dashed, chartIsSrc)
        drawLevel(pwY, dPW, "PUT WALL", colNeg, 3, line.style_solid, chartIsSrc)
        drawLevel(cwY, dCW, "CALL WALL", colPos, 3, line.style_solid, chartIsSrc)

// ── TABLEAU D'INFORMATIONS ──────────────────────────────────────────────
var table info = table.new(position.top_right, 2, 7, border_width = 1)
if barstate.islast and showTable
    color fg = chart.fg_color
    color bg = color.new(chart.bg_color, 10)
    float ageH = dTs > 0 ? (timenow - dTs) / 3600000.0 : na
    string ageTxt = na(ageH) ? "aucune donnée" : ageH < 1 ? "à jour (" + str.tostring(math.round(ageH * 60)) + " min)" : ageH < 20 ? "il y a " + str.tostring(ageH, "#.#") + " h" : "PÉRIMÉ — recopier le script"
    color ageCol = na(ageH) or ageH >= 20 ? colNeg : ageH < 1 ? color.new(#0ca30c, 0) : colFlip
    string mktTxt = mkt == "NONE" ? "non reconnu — choisir le marché" : syminfo.ticker + " → " + srcName
    bool posGamma = not na(dNet) and dNet >= 0
    table.cell(info, 0, 0, "GEX ES/NQ", text_color = fg, bgcolor = bg, text_size = size.small)
    table.cell(info, 1, 0, "CBOE", text_color = fg, bgcolor = bg, text_size = size.small)
    table.cell(info, 0, 1, "Marché", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(info, 1, 1, mktTxt, text_color = mkt == "NONE" ? colNeg : fg, bgcolor = bg, text_size = size.small)
    table.cell(info, 0, 2, "Données", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(info, 1, 2, dTs > 0 ? str.format_time(dTs, "dd/MM HH:mm", "America/New_York") + " NY" : "—", text_color = fg, bgcolor = bg, text_size = size.small)
    table.cell(info, 0, 3, "Fraîcheur", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(info, 1, 3, ageTxt, text_color = ageCol, bgcolor = bg, text_size = size.small)
    table.cell(info, 0, 4, "Régime", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(info, 1, 4, na(dNet) ? "—" : (posGamma ? "Gamma + (marché amorti) " : "Gamma − (marché volatil) ") + fmtG(dNet), text_color = posGamma ? colPos : colNeg, bgcolor = bg, text_size = size.small)
    table.cell(info, 0, 5, "Base", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(info, 1, 5, chartIsSrc ? "graphique = source" : (liveBasis ? "live ×" + str.tostring(ratio, "#.####") : "approx. (indice indisponible)"), text_color = fg, bgcolor = bg, text_size = size.small)
    table.cell(info, 0, 6, "0DTE", text_color = fg, bgcolor = bg, text_size = size.small, text_halign = text.align_left)
    table.cell(info, 1, 6, "échéance " + d0Exp, text_color = fg, bgcolor = bg, text_size = size.small)

// ── ALERTES ─────────────────────────────────────────────────────────────
alertcondition(ta.cross(close, flipY), "Croisement du gamma flip", "{{ticker}} croise le gamma flip GEX")
alertcondition(ta.crossover(high, cwY), "Test du call wall", "{{ticker}} atteint le call wall GEX")
alertcondition(ta.crossunder(low, pwY), "Test du put wall", "{{ticker}} atteint le put wall GEX")
'''


def build() -> Path:
    blocks, summaries, captured = [], [], []
    for sym in DATASETS:
        snap = latest_snapshot(sym)
        block, summary = dataset_block(sym, snap)
        blocks.append(block)
        summaries.append(summary)
        if snap:
            captured.append(snap["captured"])
    generated_iso = max(captured) if captured else datetime.now().isoformat(timespec="seconds")
    generated = generated_iso[:16].replace("T", " ") + " (New York)"
    pine = PINE_TEMPLATE.replace("{generated}", generated).replace("{data}", "\n\n".join(blocks))
    OUT.mkdir(parents=True, exist_ok=True)
    PINE_FILE.write_text(pine, encoding="utf-8")
    (OUT / "levels.json").write_text(
        json.dumps({"generated": generated_iso, "pine_file": PINE_FILE.name, "datasets": summaries}, indent=1),
        encoding="utf-8",
    )
    print(f"Indicateur TradingView régénéré : {PINE_FILE.relative_to(ROOT)} (données {generated})")
    return PINE_FILE


if __name__ == "__main__":
    build()
