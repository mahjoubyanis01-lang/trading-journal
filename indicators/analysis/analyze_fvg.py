#!/usr/bin/env python3
"""Rejoue la logique de fvg-15min.pine sur donnees reelles ES=F 15m (60j)
et mesure quelles caracteristiques de signal precedent les plus gros
mouvements, pour en deriver des filtres."""
import json, math, sys, urllib.request
import pandas as pd
import numpy as np

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=15m&range=60d"

def fetch(sym):
    req = urllib.request.Request(URL.format(sym=sym), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.load(r)
    res = j["chart"]["result"][0]
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({"t": ts, "o": q["open"], "h": q["high"], "l": q["low"],
                       "c": q["close"], "v": q["volume"]}).dropna(subset=["o", "h", "l", "c"])
    df["dt"] = pd.to_datetime(df["t"], unit="s", utc=True).dt.tz_convert("America/New_York")
    return df.reset_index(drop=True)

df = fetch("ES=F")
n = len(df)
print(f"bars: {n}  from {df.dt.iloc[0]} to {df.dt.iloc[-1]}")

o, h, l, c, v = df.o.values, df.h.values, df.l.values, df.c.values, np.nan_to_num(df.v.values)
hour = df.dt.dt.hour.values
minute = df.dt.dt.minute.values

# ATR14 (RMA) + vol sma20
tr = np.maximum(h - l, np.maximum(abs(h - np.roll(c, 1)), abs(l - np.roll(c, 1))))
tr[0] = h[0] - l[0]
atr = np.zeros(n); atr[0] = tr[0]
for i in range(1, n):
    atr[i] = (atr[i-1] * 13 + tr[i]) / 14
vsma = pd.Series(v).rolling(20).mean().values

# momentum LazyBear
L = 20
hh = pd.Series(h).rolling(L).max().values
ll = pd.Series(l).rolling(L).min().values
sma = pd.Series(c).rolling(L).mean().values
src = c - ((hh + ll) / 2 + sma) / 2
mom = np.full(n, np.nan)
x = np.arange(L)
for i in range(L - 1, n):
    y = src[i - L + 1:i + 1]
    if np.isnan(y).any():
        continue
    b, a = np.polyfit(x, y, 1)
    mom[i] = a + b * (L - 1)

# ── moteur de structure P1-P4 (port fidele) ──
tr_dir = 1; stt = 0; p1e = p1o = p2e = pp2 = pp1 = float("nan"); hp1 = False
trend = np.zeros(n, int); conf = np.zeros(n, int); p3u = np.zeros(n, bool); p3d = np.zeros(n, bool)
p4u = np.zeros(n, bool); p4d = np.zeros(n, bool)
ctrend = 0
for i in range(n):
    if math.isnan(p1e):
        tr_dir = 1 if c[i] >= o[i] else -1
        p1e = h[i] if tr_dir == 1 else l[i]
        p1o = l[i] if tr_dir == 1 else h[i]
        pp2 = p1e
    if tr_dir == 1:
        if stt == 0 and h[i] > p1e: p1e, p1o, hp1 = h[i], l[i], True
        if stt == 0 and h[i] <= p1e and l[i] < p1o: p2e, stt = l[i], 1
        if stt == 1 and l[i] < p2e: p2e = l[i]
        if stt == 1 and c[i] > p1e:
            p3u[i] = True; pp2, pp1, hp1 = p2e, float("nan"), False
            p1e, p1o, p2e, stt = h[i], l[i], float("nan"), 0
        tdn = (not math.isnan(pp2) and c[i] < pp2) or (hp1 and not math.isnan(pp1) and c[i] < pp1)
        if stt == 1 and tdn and not (c[i] > p1e):
            p4d[i] = True; pp2, pp1, hp1 = float("nan"), p1e, True
            tr_dir, stt, p1e, p1o, p2e = -1, 0, l[i], h[i], float("nan")
    if tr_dir == -1:
        if stt == 0 and l[i] < p1e: p1e, p1o, hp1 = l[i], h[i], True
        if stt == 0 and l[i] >= p1e and h[i] > p1o: p2e, stt = h[i], 1
        if stt == 1 and h[i] > p2e: p2e = h[i]
        if stt == 1 and c[i] < p1e:
            p3d[i] = True; pp2, pp1, hp1 = p2e, float("nan"), False
            p1e, p1o, p2e, stt = l[i], h[i], float("nan"), 0
        tup = (not math.isnan(pp2) and c[i] > pp2) or (hp1 and not math.isnan(pp1) and c[i] > pp1)
        if stt == 1 and tup and not (c[i] < p1e):
            p4u[i] = True; pp2, pp1, hp1 = float("nan"), p1e, True
            tr_dir, stt, p1e, p1o, p2e = 1, 0, h[i], l[i], float("nan")
    if p3u[i]: ctrend = 1
    if p3d[i]: ctrend = -1
    trend[i] = tr_dir; conf[i] = ctrend if ctrend != 0 else tr_dir

# ── zones FVG + touches + signaux (toutes caracteristiques, sans filtre) ──
zones = []   # actifs: dict
signals = []
HORIZONS = [4, 8, 16]
for i in range(2, n):
    # mitigation / touches -> signal pending
    for z in zones:
        if z["dead"]: continue
        if z["bull"] and l[i] <= z["top"]:
            z["dead"] = True; z["touch_i"] = i
        elif not z["bull"] and h[i] >= z["bot"]:
            z["dead"] = True; z["touch_i"] = i
        elif z["bull"]:
            z["max_away"] = max(z["max_away"], l[i] - z["top"])
        else:
            z["max_away"] = max(z["max_away"], z["bot"] - h[i])
    # confirmations dans la fenetre (3 barres) apres touche
    for z in zones:
        ti = z.get("touch_i")
        if ti is None or z.get("sig") or i - ti > 3: continue
        if z["bull"]:
            sweep = l[i] < z["bot"] and c[i] > z["bot"]
            flip = c[i] > o[i] and c[i-1] <= o[i-1]
        else:
            sweep = h[i] > z["top"] and c[i] < z["top"]
            flip = c[i] < o[i] and c[i-1] >= o[i-1]
        if not (sweep or flip): continue
        z["sig"] = True
        d = 1 if z["bull"] else -1
        a = atr[i] if atr[i] > 0 else 1e-9
        rec = dict(i=i, dir=d, typ=z["typ"], pl=sweep,
                   disp=z["disp"], zsize=(z["top"] - z["bot"]) / a,
                   trend_ok=(trend[i] == d), strict_ok=(conf[i] == d),
                   mom_ok=(not math.isnan(mom[i]) and not math.isnan(mom[i-1]) and ((mom[i] > mom[i-1]) if d == 1 else (mom[i] < mom[i-1]))),
                   body=(abs(c[i] - o[i]) / a),
                   beyond=(c[i] > z["top"] if d == 1 else c[i] < z["bot"]),
                   vol_ok=(not math.isnan(vsma[i]) and v[i] > vsma[i]),
                   hour=hour[i], age=ti - z["born"], away=z["max_away"] / a)
        for hz in HORIZONS:
            j = min(i + hz, n - 1)
            rec[f"fwd{hz}"] = d * (c[j] - c[i]) / a
        j16 = min(i + 16, n - 1)
        seg_h = h[i+1:j16+1]; seg_l = l[i+1:j16+1]
        rec["mfe"] = (seg_h.max() - c[i]) / a * d if d == 1 and len(seg_h) else ((c[i] - seg_l.min()) / a if len(seg_l) else 0)
        rec["mae"] = (c[i] - seg_l.min()) / a if d == 1 and len(seg_l) else ((seg_h.max() - c[i]) / a if len(seg_h) else 0)
        signals.append(rec)
    zones = [z for z in zones if not (z["dead"] and (z.get("sig") or i - z["touch_i"] > 3))]
    # creation (bougie i = C, i-2 = A), taille min 0
    a = atr[i] if atr[i] > 0 else 1e-9
    if l[i] > h[i-2]:
        typ = "C" if p3u[i] else ("R" if p4u[i] else ("C" if trend[i] == 1 else "R"))
        zones.append(dict(bull=True, top=l[i], bot=h[i-2], born=i, dead=False, sig=False,
                          max_away=0.0, disp=abs(c[i] - o[i]) / a, typ=typ))
    if h[i] < l[i-2]:
        typ = "C" if p3d[i] else ("R" if p4d[i] else ("C" if trend[i] == -1 else "R"))
        zones.append(dict(bull=False, top=l[i-2], bot=h[i], born=i, dead=False, sig=False,
                          max_away=0.0, disp=abs(c[i] - o[i]) / a, typ=typ))

S = pd.DataFrame(signals)
print(f"\nsignaux (sans filtre, confirmation flip/PL): {len(S)}")
pd.set_option("display.width", 200)

def rep(mask, name):
    sub = S[mask]
    if len(sub) < 5:
        print(f"{name:42s} n={len(sub):4d}  (trop peu)")
        return
    print(f"{name:42s} n={len(sub):4d}  fwd4={sub.fwd4.mean():+.3f}  fwd8={sub.fwd8.mean():+.3f} "
          f"fwd16={sub.fwd16.mean():+.3f}  med16={sub.fwd16.median():+.3f}  mfe={sub.mfe.mean():.2f}  mae={sub.mae.mean():.2f}  win8={(sub.fwd8>0).mean()*100:.0f}%")

print("\n== BASE ==")
rep(S.index >= 0, "tous")
rep(S.dir == 1, "achats"); rep(S.dir == -1, "ventes")
print("\n== DEPLACEMENT (bougie creatrice, x ATR) — 'grosse chute/hausse' ==")
for t in [0.5, 0.8, 1.0, 1.5, 2.0]:
    rep(S.disp >= t, f"disp >= {t}")
rep(S.disp < 0.8, "disp < 0.8")
print("\n== TAILLE DE ZONE (x ATR) ==")
for t in [0.15, 0.25, 0.4]:
    rep(S.zsize >= t, f"zsize >= {t}")
print("\n== ELOIGNEMENT AVANT TOUCHE (x ATR) ==")
for t in [0.5, 1.0, 2.0]:
    rep(S.away >= t, f"away >= {t}")
rep(S.away < 0.5, "away < 0.5")
print("\n== AGE DE LA ZONE A LA TOUCHE (barres 15m) ==")
rep(S.age <= 2, "age <= 2"); rep((S.age >= 3) & (S.age <= 20), "age 3-20"); rep(S.age > 20, "age > 20")
print("\n== CRITERES EXISTANTS ==")
rep(S.trend_ok, "tendance souple OK"); rep(~S.trend_ok, "tendance souple KO")
rep(S.strict_ok, "tendance stricte OK"); rep(~S.strict_ok, "tendance stricte KO")
rep(S.mom_ok, "momentum OK"); rep(~S.mom_ok, "momentum KO")
rep(S.body >= 0.5, "corps conf >= 0.5 ATR"); rep(S.body < 0.5, "corps conf < 0.5 ATR")
rep(S.beyond, "cloture au-dela OK"); rep(~S.beyond, "cloture au-dela KO")
rep(S.vol_ok, "volume OK"); rep(~S.vol_ok, "volume KO")
rep(S.pl, "prise de liquidite (PL)"); rep(~S.pl, "flip simple")
rep(S.typ == "C", "zone C"); rep(S.typ == "R", "zone R")
print("\n== HEURE (New York) ==")
for a_, b_ in [(0, 6), (6, 9), (9, 12), (12, 16), (16, 24)]:
    rep((S.hour >= a_) & (S.hour < b_), f"{a_:02d}h-{b_:02d}h NY")
print("\n== COMBINAISONS ==")
rep(S.strict_ok & (S.disp >= 1.0), "strict + disp>=1.0")
rep(S.strict_ok & (S.disp >= 1.0) & (S.away >= 1.0), "strict + disp>=1.0 + away>=1.0")
rep(S.strict_ok & (S.disp >= 1.0) & S.beyond, "strict + disp>=1.0 + beyond")
rep(S.strict_ok & (S.disp >= 1.0) & (S.hour >= 9) & (S.hour < 16), "strict + disp>=1.0 + 9-16h NY")
rep(S.strict_ok & S.beyond & (S.body >= 0.5), "strict + beyond + corps")
rep(S.strict_ok & (S.disp >= 1.0) & S.beyond & (S.body >= 0.5), "strict+disp+beyond+corps")
S.to_csv("signals.csv", index=False)
print("\ncsv ecrit")
