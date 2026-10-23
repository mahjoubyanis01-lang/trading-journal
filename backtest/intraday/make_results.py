#!/usr/bin/env python3
"""Résultats 2020-2026 du signal A (cassure du range d'ouverture dans le sens
de Londres) sur données 5 min Dukascopy US500 / US Tech 100.

Usage : DUKA_DIR=... MACRO_DIR=... python3 backtest/intraday/make_results.py
Sortie : backtest/intraday_results.json
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research import build, NY  # noqa: E402
import setups as S  # noqa: E402
from orb_london import orb_london, P  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "intraday_results.json"
NAMES = {"usa500idxusd": "ES", "usatechidxusd": "NQ"}


def main():
    out = {
        "generated": datetime.now(NY).isoformat(timespec="seconds"),
        "rule": orb_london.__module__ and open(Path(__file__).resolve().parent / "orb_london.py").read().split('"""')[1].strip(),
        "data": "Dukascopy US500 / US Tech 100 (CFD sur indices cash), bougies 5 min, 2020-2026 ; signaux identiques sur les futures ES/NQ (vérifié sur 60 jours Yahoo)",
        "markets": {},
    }
    all_daily = {}
    for inst, p in P.items():
        m = NAMES[inst]
        days = build(inst)
        tr = [t for D in days for t in orb_london(D, p)]
        by_year = {}
        for y in sorted({D.d.year for D in days}):
            nd = sum(1 for D in days if D.d.year == y)
            by_year[str(y)] = S.summ([t for t in tr if t.d.year == y], nd)
        disc = [t for t in tr if t.d.year <= 2022]
        val = [t for t in tr if t.d.year >= 2023]
        out["markets"][m] = {
            "period": [days[0].d.isoformat(), days[-1].d.isoformat()],
            "summary": S.summ(tr, len(days)),
            "by_year": by_year,
            "discovery_2020_2022": S.summ(disc),
            "validation_2023_2026": S.summ(val),
            "longs": S.summ([t for t in tr if t.side > 0]),
            "shorts": S.summ([t for t in tr if t.side < 0]),
            "trades": [
                {"date": t.d.isoformat(), "time": f"{t.m // 60:02d}:{t.m % 60:02d}", "side": t.side,
                 "entry": round(t.entry, 2), "stop": round(t.stop, 2), "target": round(t.tgt, 2),
                 "exit": round(t.exit, 2), "why": t.why, "r": round(t.r, 3)}
                for t in tr
            ],
        }
        for t in tr:
            all_daily.setdefault(t.d, []).append(t)
        print(m, out["markets"][m]["summary"])
    comb = [t for d in sorted(all_daily) for t in all_daily[d]]
    out["portfolio"] = {
        "summary": S.summ(comb),
        "by_year": {str(y): S.summ([t for t in comb if t.d.year == y]) for y in sorted({t.d.year for t in comb})},
    }
    print("portefeuille ES+NQ", out["portfolio"]["summary"])
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"écrit : {OUT}")


if __name__ == "__main__":
    main()
