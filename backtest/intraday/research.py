"""Cadre de recherche intraday ES/NQ (données Dukascopy US500 / US Tech 100, 5 min).

Journée de trading D : 18h00 (D-1) -> 17h00 (D), heure de New York.
Séances (NY) : Asie 18:00-02:00 · Londres 02:00-08:30 · pré-ouverture 08:30-09:30
               NY matin 09:30-12:00 · NY après-midi 12:00-16:00
"""
import csv
import os
from pathlib import Path
import glob
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
DUKA = os.environ.get("DUKA_DIR", str(Path(__file__).resolve().parent / "data" / "dukascopy"))
MACRO = os.environ.get("MACRO_DIR", str(Path(__file__).resolve().parent / "data" / "macro"))


@dataclass
class B:
    t: datetime
    o: float
    h: float
    l: float
    c: float
    v: float
    m: int = 0       # minute du jour NY


def load_duka(inst):
    out = []
    for f in sorted(glob.glob(f"{DUKA}/{inst}_*.json")):
        for ts, o, h, l, c, v in json.load(open(f)):
            t = datetime.fromtimestamp(ts / 1000, NY)
            out.append(B(t, o, h, l, c, v or 0.0, t.hour * 60 + t.minute))
    out.sort(key=lambda b: b.t)
    dedup = []
    for b in out:
        if not dedup or b.t != dedup[-1].t:
            dedup.append(b)
    return dedup


def tday(t):
    d = t.date()
    if t.hour >= 18:
        d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


@dataclass
class Day:
    d: date
    bars: list = field(default_factory=list)
    lv: dict = field(default_factory=dict)
    f: dict = field(default_factory=dict)


def sl(bars, a, b):
    """barres dont la minute NY est dans [a, b) (gère le passage de minuit si a > b)."""
    if a <= b:
        return [x for x in bars if a <= x.m < b]
    return [x for x in bars if x.m >= a or x.m < b]


def hl(bs):
    return (max(x.h for x in bs), min(x.l for x in bs)) if bs else (None, None)


def build(inst):
    bars = load_duka(inst)
    days = {}
    for b in bars:
        days.setdefault(tday(b.t), Day(tday(b.t))).bars.append(b)
    out = []
    prev = None
    closes = []
    for d in sorted(days):
        D = days[d]
        rth = sl(D.bars, 570, 960)
        if len(rth) < 70 or sum(1 for x in rth if x.m < 585) < 3:   # séance incomplète / trou à l'ouverture
            continue
        D.rth = rth
        asia = sl(D.bars, 1080, 120)
        lon = sl(D.bars, 120, 510)
        on = [x for x in D.bars if x.m >= 1080 or x.m < 570]
        lv = D.lv
        lv["ASH"], lv["ASL"] = hl(asia)
        lv["LDH"], lv["LDL"] = hl(lon)
        lv["ONH"], lv["ONL"] = hl(on)
        lv["OPEN"] = rth[0].o
        lv["ORH"], lv["ORL"] = hl([x for x in rth if x.m < 585])
        lv["IBH"], lv["IBL"] = hl([x for x in rth if x.m < 630])
        if prev is not None:
            lv["PDH"], lv["PDL"] = hl(prev.rth)
            lv["PDC"] = prev.rth[-1].c
        # VWAP de séance cash (volume tick)
        pv = vol = 0.0
        D.vwap = []
        for x in rth:
            tp = (x.h + x.l + x.c) / 3
            w = x.v if x.v > 0 else 1.0
            pv += tp * w
            vol += w
            D.vwap.append(pv / vol)
        # ---- variables connues avant 9h30 ----
        f = D.f
        pre = [x for x in on if x.m < 570 or x.m >= 1080]
        if prev is not None and pre:
            pdc = lv["PDC"]
            f["ret_on"] = (pre[-1].c - pdc) / pdc
            lond = [x for x in pre if 120 <= x.m < 570]
            f["ret_lon"] = (lond[-1].c - lond[0].o) / lond[0].o if lond else 0.0
            f["gap"] = (rth[0].o - pdc) / pdc
            ph, pl_ = lv["PDH"], lv["PDL"]
            f["clv_prev"] = (pdc - pl_) / (ph - pl_) - 0.5 if ph > pl_ else 0.0
            f["ret_prev"] = (pdc - prev.rth[0].o) / prev.rth[0].o
            f["open_vs_pd"] = 1 if rth[0].o > ph else -1 if rth[0].o < pl_ else 0
            # signature d'annonce macro de 8h30 : bougie 8h30 >> bruit pré-marché
            b830 = [x for x in D.bars if x.m == 510]
            base = [x.h - x.l for x in D.bars if 420 <= x.m < 510]
            if b830 and base:
                med = sorted(base)[len(base) // 2] or 1e-9
                f["ev830"] = (b830[0].h - b830[0].l) / med
            else:
                f["ev830"] = 0.0
        if len(closes) >= 20:
            sma20 = sum(closes[-20:]) / 20
            f["trend20"] = 1 if closes[-1] > sma20 else -1
            f["dist20"] = (closes[-1] - sma20) / sma20
        if len(closes) >= 50:
            f["trend50"] = 1 if closes[-1] > sum(closes[-50:]) / 50 else -1
        # ---- cibles ----
        D.y_rth = (rth[-1].c - rth[0].o) / rth[0].o
        am = [x for x in rth if x.m < 720]
        pm = [x for x in rth if x.m >= 720]
        D.y_am = (am[-1].c - am[0].o) / am[0].o
        D.y_pm = (pm[-1].c - pm[0].o) / pm[0].o if pm else 0.0
        closes.append(rth[-1].c)
        out.append(D)
        prev = D
    return out


def load_macro():
    """Séries journalières : VIX, VIX3M, VIX9D, taux 10 ans, 2 ans, dollar."""
    m = {}
    for s in ("VIX", "VIX3M", "VIX9D"):
        for r in csv.DictReader(open(f"{MACRO}/{s}.csv")):
            try:
                d = datetime.strptime(r["DATE"], "%m/%d/%Y").date()
                m.setdefault(d, {})[s] = float(r["CLOSE"])
            except (ValueError, KeyError):
                pass
    for s in ("DGS10", "DGS2", "DTWEXBGS"):
        for r in csv.DictReader(open(f"{MACRO}/{s}.csv")):
            try:
                d = datetime.strptime(r["observation_date"], "%Y-%m-%d").date()
                m.setdefault(d, {})[s] = float(r[s])
            except (ValueError, KeyError):
                pass
    fomc = set(datetime.strptime(x, "%Y-%m-%d").date() for x in json.load(open(f"{MACRO}/fomc_dates.json")))
    return m, fomc


def add_macro(days, macro, fomc):
    """Ajoute les variables macro connues AVANT l'ouverture (valeurs de la veille)."""
    mdates = sorted(macro)
    import bisect
    for D in days:
        i = bisect.bisect_left(mdates, D.d) - 1       # dernier jour STRICTEMENT avant D
        prevd = [mdates[j] for j in range(max(0, i - 6), i + 1)]
        def last(key, k=0):
            vals = [macro[x][key] for x in prevd if key in macro[x]]
            return vals[-1 - k] if len(vals) > k else None
        vix, vix_1 = last("VIX"), last("VIX", 1)
        v3m = last("VIX3M")
        if vix:
            D.f["vix"] = vix
            if vix_1:
                D.f["vix_chg"] = vix - vix_1
            if v3m:
                D.f["vix_ts"] = vix / v3m            # > 1 : structure inversée (stress)
        y10, y10_1 = last("DGS10"), last("DGS10", 1)
        if y10 is not None and y10_1 is not None:
            D.f["y10_chg"] = y10 - y10_1
        dx, dx_1 = last("DTWEXBGS"), last("DTWEXBGS", 1)
        if dx and dx_1:
            D.f["usd_chg"] = (dx - dx_1) / dx_1
        D.f["fomc"] = 1 if D.d in fomc else 0
        D.f["dow"] = D.d.weekday()
