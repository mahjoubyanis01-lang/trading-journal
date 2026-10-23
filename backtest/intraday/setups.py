"""Setups intraday 5 min sur la séance cash (9h30-16h NY). Chaque fonction
renvoie la liste des trades d'une journée ; `bias` = +1 / -1 / 0 (0 = pas de filtre)."""
from dataclasses import dataclass


@dataclass
class T:
    d: object
    m: int          # minute NY d'entrée
    side: int
    entry: float
    stop: float
    tgt: float
    tag: str
    exit: float = 0.0
    r: float = 0.0
    why: str = ""


def sim(t, bars, cost):
    risk = abs(t.entry - t.stop)
    for b in bars:
        if b.m >= 955:                       # sortie 15h55
            t.exit, t.why = b.o, "eod"
            break
        if t.side > 0:
            if b.l <= t.stop:
                t.exit, t.why = t.stop, "stop"; break
            if b.h >= t.tgt:
                t.exit, t.why = t.tgt, "tgt"; break
        else:
            if b.h >= t.stop:
                t.exit, t.why = t.stop, "stop"; break
            if b.l <= t.tgt:
                t.exit, t.why = t.tgt, "tgt"; break
    else:
        t.exit, t.why = (bars[-1].c if bars else t.entry), "eod"
    t.r = (t.side * (t.exit - t.entry) - cost) / risk
    return t


def orb(D, bias, P, or_min=15, stop="mid", R=2.0, last_entry=690):
    rth, lv = D.rth, D.lv
    H, L = (lv["ORH"], lv["ORL"]) if or_min == 15 else (lv["IBH"], lv["IBL"]) if or_min == 60 else \
        (max(x.h for x in rth if x.m < 570 + or_min), min(x.l for x in rth if x.m < 570 + or_min))
    for i, b in enumerate(rth):
        if b.m < 570 + or_min or b.m >= last_entry:
            continue
        s = 1 if b.c > H else -1 if b.c < L else 0
        if s == 0:
            continue
        if bias and s != bias:
            return []
        st = (H + L) / 2 if stop == "mid" else (L if s > 0 else H)
        risk = abs(b.c - st)
        if not (P["min_risk"] <= risk <= P["max_risk"]):
            return []
        return [sim(T(D.d, b.m, s, b.c, st, b.c + s * R * risk, f"ORB{or_min}"), rth[i + 1:], P["cost"])]
    return []


def sweep(D, bias, P, levels, R=2.0, start=570, end=690, max_n=1, tgt="R"):
    """Mèche au-delà d'un niveau de séance puis clôture de retour à l'intérieur."""
    rth, lv = D.rth, D.lv
    used, out = set(), []
    for i, b in enumerate(rth):
        if not (start <= b.m < end) or len(out) >= max_n:
            continue
        for n in levels:
            L = lv.get(n)
            if L is None or n in used:
                continue
            hi_level = n.endswith("H")
            if hi_level and b.h > L + P["pen"] and b.c < L:
                s, ext = -1, b.h
            elif not hi_level and b.l < L - P["pen"] and b.c > L:
                s, ext = 1, b.l
            else:
                if (hi_level and b.c > L + P["pen"]) or (not hi_level and b.c < L - P["pen"]):
                    used.add(n)          # niveau accepté : plus de fade
                continue
            used.add(n)
            if bias and s != bias:
                continue
            st = ext - s * P["tick"] * 2
            risk = abs(b.c - st)
            if not (P["min_risk"] <= risk <= P["max_risk"]):
                continue
            target = b.c + s * R * risk
            if tgt == "vwap":
                vw = D.vwap[i]
                if s * (vw - b.c) >= risk:
                    target = vw
            out.append(sim(T(D.d, b.m, s, b.c, st, target, "SW_" + n), rth[i + 1:], P["cost"]))
            break
    return out


def break_retest(D, bias, P, levels, R=2.0, start=585, end=900, max_n=1):
    rth, lv = D.rth, D.lv
    state = {}
    out = []
    for i in range(2, len(rth)):
        b, p, pp = rth[i], rth[i - 1], rth[i - 2]
        if not (start <= b.m < end) or len(out) >= max_n:
            continue
        for n in levels:
            L = lv.get(n)
            if L is None:
                continue
            st, sd = state.get(n, (0, 0))
            if st == 0:
                if pp.c <= L < p.c and b.c > L:
                    state[n] = (1, 1)
                elif pp.c >= L > p.c and b.c < L:
                    state[n] = (1, -1)
            elif st == 1:
                if (sd > 0 and b.l <= L + P["tol"]) or (sd < 0 and b.h >= L - P["tol"]):
                    state[n] = (2, sd)
                    if sd * (b.c - L) > 0 and (not bias or sd == bias):
                        stp = L - sd * P["stop_off"]
                        risk = abs(b.c - stp)
                        if P["min_risk"] <= risk <= P["max_risk"]:
                            out.append(sim(T(D.d, b.m, sd, b.c, stp, b.c + sd * R * risk, "BR_" + n), rth[i + 1:], P["cost"]))
                            break
    return out


def vwap_pullback(D, bias, P, R=2.0, start=600, end=870):
    """Journée directionnelle : prix du côté du biais par rapport au VWAP, nouveau
    plus haut (bas) de séance, puis premier repli qui touche le VWAP et clôture
    du bon côté."""
    if not bias:
        return []
    rth = D.rth
    ext = None
    armed = False
    for i, b in enumerate(rth):
        vw = D.vwap[i]
        if b.m < start:
            if ext is None:
                ext = b.h if bias > 0 else b.l
            else:
                ext = max(ext, b.h) if bias > 0 else min(ext, b.l)
            continue
        if b.m >= end:
            return []
        if bias > 0:
            if b.h > ext:
                ext = b.h
                armed = b.c > vw
            elif armed and b.l <= vw and b.c > vw:
                st = min(b.l, vw) - P["stop_off"] / 2
                risk = b.c - st
                if P["min_risk"] <= risk <= P["max_risk"]:
                    return [sim(T(D.d, b.m, 1, b.c, st, b.c + R * risk, "VWAP"), rth[i + 1:], P["cost"])]
                return []
        else:
            if b.l < ext:
                ext = b.l
                armed = b.c < vw
            elif armed and b.h >= vw and b.c < vw:
                st = max(b.h, vw) + P["stop_off"] / 2
                risk = st - b.c
                if P["min_risk"] <= risk <= P["max_risk"]:
                    return [sim(T(D.d, b.m, -1, b.c, st, b.c - R * risk, "VWAP"), rth[i + 1:], P["cost"])]
                return []
    return []


def summ(tr, ndays=None):
    if not tr:
        return {"n": 0}
    rs = [t.r for t in tr]
    w = [r for r in rs if r > 0]
    lo = [r for r in rs if r <= 0]
    eq = pk = dd = 0.0
    for r in rs:
        eq += r; pk = max(pk, eq); dd = min(dd, eq - pk)
    s = {"n": len(rs), "win": round(100 * len(w) / len(rs), 1), "avgR": round(sum(rs) / len(rs), 3),
         "totR": round(sum(rs), 1), "PF": round(sum(w) / -sum(lo), 2) if sum(lo) < 0 else 99, "dd": round(dd, 1)}
    if ndays:
        s["per_day"] = round(len(rs) / ndays, 2)
    return s
