#!/usr/bin/env python3
"""Backtest de référence des signaux ES/NQ de l'indicateur TradingView.

Implémentation barre par barre sur bougies 1 h, dans le MÊME ordre d'opérations
que le moteur Pine (fonction `engine` de tradingview/GEX_Levels_ES_NQ.pine).

Règle du signal « cassure validée + retest dans la tendance » :
  - PDH / PDL : plus haut / plus bas de la séance cash de la veille
    (bougies 1 h de 10h à 15h, heure de New York) ;
  - tendance : clôture de la veille au-dessus (haussière) ou en dessous
    (baissière) de la moyenne des 20 dernières clôtures ;
  - cassure ACCEPTÉE : 2 clôtures 1 h consécutives au-delà du niveau, après
    une clôture en deçà ;
  - RETEST : une bougie revient toucher le niveau (à `tol` près) et clôture du
    bon côté -> entrée à la clôture, uniquement dans le sens de la tendance ;
  - stop : niveau -/+ stop_off ; objectif : 2R ; sortie forcée à 16h00 NY ;
  - fenêtre de signal : bougies de 10h à 14h NY ; 1 signal maximum par jour ;
  - frais : 0,5 pt ES / 2 pts NQ par aller-retour (slippage + commission).

Données : Yahoo Finance (ES=F, NQ=F), bougies 1 h sur 2 ans.
Sortie  : backtest/results.json (statistiques + liste des trades).
Usage   : python3 backtest/signals_backtest.py [-v]
"""
import json
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
OUT = Path(__file__).resolve().parent / "results.json"
MARKETS = {
    "ES": dict(yahoo="ES=F", tol=2.0, stop_off=6.0, min_risk=3.0, max_risk=30.0, cost=0.5),
    "NQ": dict(yahoo="NQ=F", tol=8.0, stop_off=24.0, min_risk=12.0, max_risk=120.0, cost=2.0),
}
SMA, RR = 20, 2.0


def fetch_bars(symbol: str):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
           "?interval=1h&range=730d&includePrePost=true")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60, context=ssl.create_default_context()) as r:
        d = json.load(r)["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    now = datetime.now(NY).timestamp()
    bars = []
    for i, ts in enumerate(d["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        # bougie encore en cours (non clôturée) : exclue, comme dans le moteur Pine
        if ts % 3600 != 0 or ts + 3600 > now:
            continue
        bars.append((datetime.fromtimestamp(ts, NY), o, h, l, c))
    return bars


def run(bars, p):
    closes, trades = [], []
    rth_day = cur_h = cur_l = cur_c = pdh = pdl = None
    trend, c1, c2, done = 0, None, None, False
    st, sd = {"H": 0, "L": 0}, {"H": 0, "L": 0}
    trade = None

    def close_trade(px, why):
        nonlocal trade
        trade.update(exit=round(px, 2), why=why,
                     r=round((trade["side"] * (px - trade["entry"]) - p["cost"]) / trade["risk"], 3))
        trades.append(trade)
        trade = None

    for t, o, h, l, c in bars:
        if not (10 <= t.hour <= 15 and t.weekday() < 5):
            continue
        d = t.date()
        if d != rth_day:
            if trade:
                close_trade(cur_c, "fin de données")
            if rth_day is not None:
                pdh, pdl = cur_h, cur_l
                closes.append(cur_c)
                trend = (1 if closes[-1] > sum(closes[-SMA:]) / SMA else -1) if len(closes) >= SMA else 0
            rth_day, cur_h, cur_l, c1, c2, done = d, h, l, None, None, False
            st = {"H": 0, "L": 0}
        if trade:
            s = trade["side"]
            if (s > 0 and l <= trade["stop"]) or (s < 0 and h >= trade["stop"]):
                close_trade(trade["stop"], "stop")
            elif (s > 0 and h >= trade["target"]) or (s < 0 and l <= trade["target"]):
                close_trade(trade["target"], "objectif")
            if trade and t.hour == 15:
                close_trade(c, "clôture")
        if t.hour <= 14 and not done and pdh is not None and trend != 0:
            for k, L in (("H", pdh), ("L", pdl)):
                if done:
                    break
                if st[k] == 0:
                    if c2 is not None and c2 <= L < c1 and c > L:
                        st[k], sd[k] = 1, 1
                    elif c2 is not None and c2 >= L > c1 and c < L:
                        st[k], sd[k] = 1, -1
                elif st[k] == 1:
                    s = sd[k]
                    if (s > 0 and l <= L + p["tol"]) or (s < 0 and h >= L - p["tol"]):
                        if s * (c - L) > 0 and s == trend:
                            stop = L - s * p["stop_off"]
                            risk = abs(c - stop)
                            if p["min_risk"] <= risk <= p["max_risk"]:
                                trade = dict(date=d.isoformat(), time=t.strftime("%H:%M"), side=s,
                                             level="PDH" if k == "H" else "PDL", level_px=round(L, 2),
                                             entry=round(c, 2), stop=round(stop, 2),
                                             target=round(c + s * RR * risk, 2), risk=round(risk, 2))
                                done = True
                        st[k] = 2
        cur_h, cur_l, cur_c = max(cur_h, h), min(cur_l, l), c
        c2, c1 = c1, c
    return trades, trade


def summarize(trades):
    rs = [t["r"] for t in trades]
    if not rs:
        return {"n": 0}
    w = [r for r in rs if r > 0]
    lo = [r for r in rs if r <= 0]
    eq = pk = dd = 0.0
    for r in rs:
        eq += r
        pk = max(pk, eq)
        dd = min(dd, eq - pk)
    return {
        "n": len(rs),
        "win_rate": round(100 * len(w) / len(rs), 1),
        "expectancy_r": round(sum(rs) / len(rs), 3),
        "total_r": round(sum(rs), 2),
        "profit_factor": round(sum(w) / -sum(lo), 2) if sum(lo) < 0 else None,
        "max_drawdown_r": round(dd, 2),
    }


def main():
    out = {"generated": datetime.now(NY).isoformat(timespec="seconds"), "rule": __doc__.split("Données")[0].strip(), "markets": {}}
    for m, p in MARKETS.items():
        bars = fetch_bars(p["yahoo"])
        trades, open_trade = run(bars, p)
        by_year = {}
        for t in trades:
            by_year.setdefault(t["date"][:4], []).append(t)
        out["markets"][m] = {
            "period": [bars[0][0].date().isoformat(), bars[-1][0].date().isoformat()],
            "summary": summarize(trades),
            "by_year": {y: summarize(v) for y, v in sorted(by_year.items())},
            "longs": summarize([t for t in trades if t["side"] > 0]),
            "shorts": summarize([t for t in trades if t["side"] < 0]),
            "trades": trades,
            "open_trade": open_trade,
        }
        s = out["markets"][m]["summary"]
        print(f"{m} {out['markets'][m]['period']}: {s}")
        if open_trade:
            print(f"   trade en cours : {open_trade}")
        if "-v" in sys.argv:
            for t in trades:
                print(f"   {t['date']} {t['time']} {'ACHAT' if t['side'] > 0 else 'VENTE'} {t['level']} "
                      f"entrée {t['entry']} stop {t['stop']} obj {t['target']} -> {t['why']} {t['r']:+.2f}R")
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Résultats écrits dans {OUT}")


if __name__ == "__main__":
    main()
