"""Signal A : cassure du range d'ouverture (9h30-9h45 NY) dans le sens de la
séance de Londres (2h00 -> 9h25 NY). Première clôture 5 min hors du range avant
11h30 : trade si elle va dans le sens de Londres (sinon rien ce jour-là).
VENTES seulement si la tendance 20 jours est baissière (short_filter=True).
Stop au milieu du range, objectif 2R, sortie au plus tard à 15h55.
(La variante « seconde chance » après un stop a été testée et rejetée.)"""
import os, sys
from research import build
import setups as S
P = {"usa500idxusd": dict(min_risk=2.0, max_risk=25.0, cost=0.5), "usatechidxusd": dict(min_risk=8.0, max_risk=100.0, cost=2.0)}

def lon_bias(D):
    bs = [x for x in D.bars if 120 <= x.m < 565]
    r = (bs[-1].c - bs[0].o) if bs else 0
    return 1 if r > 0 else -1 if r < 0 else 0

def orb_london(D, p, second=False, R=2.0, last=690, short_filter=True):
    rth = D.rth
    bias = lon_bias(D)
    if not bias: return []
    orb = [x for x in rth if x.m < 585]
    H, L = max(x.h for x in orb), min(x.l for x in orb)
    out = []
    i = 0
    while i < len(rth):
        b = rth[i]
        if b.m < 585 or b.m >= last:
            i += 1; continue
        s = 1 if b.c > H else -1 if b.c < L else 0
        if s == 0:
            i += 1; continue
        if s != bias: return out          # première cassure contre le biais : pas de trade
        if s < 0 and short_filter and D.f.get("trend20") != -1: return out   # vente hors tendance baissière
        st = (H + L) / 2
        risk = abs(b.c - st)
        if not (p["min_risk"] <= risk <= p["max_risk"]): return out
        t = S.sim(S.T(D.d, b.m, s, b.c, st, b.c + s * R * risk, "ORB"), rth[i + 1:], p["cost"])
        out.append(t)
        if not second or t.why != "stop" or len(out) >= 2: return out
        # seconde chance : attendre le retour DANS le range puis une nouvelle clôture hors range
        j = i + 1
        while j < len(rth) and not (L <= rth[j].c <= H): j += 1
        i = j + 1
    return out

if __name__ == "__main__":
    YEARS = [int(y) for y in os.environ.get("YEARS", "2025,2026").split(",")]
    for second in (False, True):
        print("seconde chance" if second else "un seul trade")
        for inst in P:
            days = [D for D in build(inst) if D.d.year in YEARS]
            tr = [t for D in days for t in orb_london(D, P[inst], second)]
            s = S.summ(tr, len(days))
            print(f"  {inst[:6]} {s} | par année:", {y: S.summ([t for t in tr if t.d.year == y]).get('avgR') for y in YEARS})
