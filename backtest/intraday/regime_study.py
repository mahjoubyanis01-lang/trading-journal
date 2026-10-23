"""Filtres de régime pour le setup A (ORB15 + biais Londres), fixés à l'avance :
  F1 range d'ouverture étroit : largeur OR < médiane des 20 derniers OR
  F2 veille comprimée          : range cash veille < moyenne des 10 derniers ranges
  F3 volatilité en hausse      : VIX veille > moyenne VIX des 20 jours précédents
Découverte 2020-2022, validation 2023-2026 (jamais utilisée pour choisir)."""
import statistics
from research import build, load_macro, add_macro
import setups as S
from orb_london import orb_london, P

macro, fomc = load_macro()
vix_dates = sorted(d for d in macro if "VIX" in macro[d])


def vix_rising(D):
    import bisect
    i = bisect.bisect_left(vix_dates, D.d) - 1
    if i < 21:
        return None
    last = macro[vix_dates[i]]["VIX"]
    avg = sum(macro[vix_dates[j]]["VIX"] for j in range(i - 20, i)) / 20
    return last > avg


res = {}
for inst, p in P.items():
    days = build(inst)
    add_macro(days, macro, fomc)
    orw, rng = [], []
    rows = []
    for D in days:
        orb = [x for x in D.rth if x.m < 585]
        w = max(x.h for x in orb) - min(x.l for x in orb)
        f1 = (w < statistics.median(orw[-20:])) if len(orw) >= 20 else None
        f2 = (rng[-1] < sum(rng[-11:-1]) / 10) if len(rng) >= 11 else None
        f3 = vix_rising(D)
        tr = orb_london(D, p)
        rows.append((D.d.year, f1, f2, f3, tr))
        orw.append(w)
        rng.append(max(x.h for x in D.rth) - min(x.l for x in D.rth))
    res[inst] = rows


def show(label, pick):
    line = f"{label:<38}"
    for inst, rows in res.items():
        for part, yrs in (("découverte 20-22", (2020, 2021, 2022)), ("validation 23-26", (2023, 2024, 2025, 2026))):
            tr = [t for y, f1, f2, f3, ts in rows if y in yrs and pick(f1, f2, f3) for t in ts]
            nd = sum(1 for y, *_ in rows if y in yrs)
            s = S.summ(tr, nd)
            line += f" | {inst[:6]} {part}: n={s.get('n',0):>3} R={s.get('avgR','-'):>6} PF={s.get('PF','-'):>5}"
        yearly = {}
        for y, f1, f2, f3, ts in rows:
            if pick(f1, f2, f3):
                yearly.setdefault(y, []).extend(ts)
        line += " ans[" + " ".join(f"{y % 100}:{S.summ(v).get('avgR', '-')}" for y, v in sorted(yearly.items())) + "]"
    print(line)


show("aucun filtre", lambda a, b, c: True)
show("F1 range d'ouverture étroit", lambda a, b, c: a is True)
show("F1 inverse (range large)", lambda a, b, c: a is False)
show("F2 veille comprimée", lambda a, b, c: b is True)
show("F2 inverse (veille large)", lambda a, b, c: b is False)
show("F3 VIX en hausse", lambda a, b, c: c is True)
show("F3 inverse (VIX en baisse)", lambda a, b, c: c is False)
