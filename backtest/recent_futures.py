#!/usr/bin/env python3
"""Suivi glissant du signal A sur les VRAIS futures ES / NQ (60 derniers jours,
bougies 5 min Yahoo Finance), avec exactement la même logique que le backtest
2020-2026 (backtest/intraday/orb_london.py).

Sortie : backtest/recent_results.json
Usage  : python3 backtest/recent_futures.py
"""
import json
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "intraday"))
import research as R  # noqa: E402
import setups as S  # noqa: E402
from orb_london import orb_london, P  # noqa: E402

OUT = HERE / "recent_results.json"
MARKETS = {"ES": ("ES=F", "usa500idxusd"), "NQ": ("NQ=F", "usatechidxusd")}


def fetch(symbol):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
           "?interval=5m&range=60d&includePrePost=true")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60, context=ssl.create_default_context()) as r:
        d = json.load(r)["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    now = datetime.now(R.NY).timestamp()
    bars = []
    for i, ts in enumerate(d["timestamp"]):
        o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if None in (o, h, l, c) or ts % 300 != 0 or ts + 300 > now:   # bougie non clôturée exclue
            continue
        t = datetime.fromtimestamp(ts, R.NY)
        bars.append(R.B(t, o, h, l, c, v or 0, t.hour * 60 + t.minute))
    return bars


def main():
    out = {"generated": datetime.now(R.NY).isoformat(timespec="seconds"),
           "source": "Yahoo Finance ES=F / NQ=F, bougies 5 min, 60 derniers jours", "markets": {}}
    for m, (sym, inst) in MARKETS.items():
        bars = fetch(sym)
        R.load_duka = lambda _i, b=bars: b
        days = R.build(inst)
        tr = [t for D in days for t in orb_london(D, P[inst])]
        out["markets"][m] = {
            "period": [days[0].d.isoformat(), days[-1].d.isoformat()] if days else None,
            "summary": S.summ(tr, len(days)),
            "trades": [{"date": t.d.isoformat(), "time": f"{t.m // 60:02d}:{t.m % 60:02d}", "side": t.side,
                        "entry": round(t.entry, 2), "stop": round(t.stop, 2), "target": round(t.tgt, 2),
                        "exit": round(t.exit, 2), "why": t.why, "r": round(t.r, 3)} for t in tr],
        }
        print(m, out["markets"][m]["period"], out["markets"][m]["summary"])
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
