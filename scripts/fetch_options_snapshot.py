#!/usr/bin/env python3
"""Snapshot des chaînes d'options CBOE (données différées, gratuites) + calcul GEX.

Source : https://cdn.cboe.com/api/global/delayed_quotes/options/<SYMBOL>.json
Sortie : data/options/<SYM>/<YYYY-MM-DD>/<HHMM>.json   (snapshot agrégé par strike)
         data/options/<SYM>/<YYYY-MM-DD>/day.json      (index des snapshots du jour)
         data/options/<SYM>/days.json                  (liste des jours disponibles)
         data/options/manifest.json                    (symboles + dernier jour)

GEX par contrat = gamma * open_interest * 100 * spot^2 * 0.01  (dollar-gamma pour
un mouvement de 1% du sous-jacent), calls positifs / puts négatifs (convention
dealer long calls / short puts). Stocké en millions de dollars.

Usage : python3 scripts/fetch_options_snapshot.py [--force] [SYM ...]
  --force : enregistre même hors heures de marché / données inchangées.
"""
import json
import re
import ssl
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "options"
CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{cboe}.json"
OPT_RE = re.compile(r"^[A-Z]+(\d{6})([CP])(\d{8})$")

# Par symbole : code CBOE, fenêtre de strikes autour du spot, DTE max retenu.
SYMBOLS = {
    "SPX": {"cboe": "_SPX", "pct_range": 0.07, "max_dte": 45},  # S&P 500 (indice)
    "SPY": {"cboe": "SPY", "pct_range": 0.07, "max_dte": 45},   # S&P 500 (ETF)
    "NDX": {"cboe": "_NDX", "pct_range": 0.07, "max_dte": 45},  # Nasdaq 100 (indice)
    "QQQ": {"cboe": "QQQ", "pct_range": 0.07, "max_dte": 45},   # Nasdaq 100 (ETF)
}


def fetch(cboe_sym: str) -> dict:
    url = CBOE_URL.format(cboe=cboe_sym)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return json.load(r)


def parse_option(sym: str):
    """'SPX261120C00400000' -> (date_exp 'YYYY-MM-DD', 'C'|'P', strike)."""
    m = OPT_RE.match(sym)
    if not m:
        return None
    ymd, cp, strike = m.groups()
    exp = f"20{ymd[0:2]}-{ymd[2:4]}-{ymd[4:6]}"
    return exp, cp, int(strike) / 1000.0


def build_snapshot(sym: str, cfg: dict, raw: dict, now_ny: datetime) -> dict:
    data = raw["data"]
    spot = float(data["current_price"])
    lo, hi = spot * (1 - cfg["pct_range"]), spot * (1 + cfg["pct_range"])
    today = now_ny.date()

    per_strike: dict[float, list[float]] = {}  # strike -> [cGex,pGex,cOI,pOI,cVol,pVol,cDex,pDex]
    per_exp: dict[str, float] = {}             # expiration -> net GEX

    for o in data["options"]:
        parsed = parse_option(o["option"])
        if not parsed:
            continue
        exp, cp, strike = parsed
        if not (lo <= strike <= hi):
            continue
        exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
        dte = (exp_date - today).days
        if dte < 0 or dte > cfg["max_dte"]:
            continue
        oi = float(o.get("open_interest") or 0)
        gamma = float(o.get("gamma") or 0)
        delta = float(o.get("delta") or 0)
        vol = float(o.get("volume") or 0)
        # dollar-gamma / dollar-delta pour 1% de move, en millions
        gex = gamma * oi * 100 * spot * spot * 0.01 / 1e6
        dex = delta * oi * 100 * spot * 0.01 / 1e6  # delta des puts déjà négatif
        row = per_strike.setdefault(strike, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        if cp == "C":
            row[0] += gex
            row[2] += oi
            row[4] += vol
            row[6] += dex
            per_exp[exp] = per_exp.get(exp, 0.0) + gex
        else:
            row[1] -= gex
            row[3] += oi
            row[5] += vol
            row[7] += dex
            per_exp[exp] = per_exp.get(exp, 0.0) - gex

    strikes = sorted(per_strike)
    call_gex = [round(per_strike[k][0], 3) for k in strikes]
    put_gex = [round(per_strike[k][1], 3) for k in strikes]
    net = [c + p for c, p in zip(call_gex, put_gex)]

    # Flip gamma : changement de signe du profil GEX net le plus proche du spot
    # (interpolation linéaire entre les deux strikes encadrant le zéro)
    flip = None
    candidates = []
    for i in range(1, len(net)):
        a, b = net[i - 1], net[i]
        if a * b < 0:
            t = a / (a - b)
            candidates.append(strikes[i - 1] + t * (strikes[i] - strikes[i - 1]))
        elif a != 0 and b == 0:
            candidates.append(strikes[i])
    if candidates:
        flip = round(min(candidates, key=lambda k: abs(k - spot)), 2)

    call_wall = strikes[call_gex.index(max(call_gex))] if strikes else None
    put_wall = strikes[put_gex.index(min(put_gex))] if strikes else None

    return {
        "symbol": sym,
        "cboe": cfg["cboe"],
        "spot": spot,
        "cboe_timestamp": raw.get("timestamp"),
        "last_trade_time": data.get("last_trade_time"),
        "captured": now_ny.isoformat(timespec="seconds"),
        "day": today.isoformat(),
        "time": now_ny.strftime("%H%M"),
        "iv30": data.get("iv30"),
        "unit": "GEX en millions USD par mouvement de 1%",
        "strikes": strikes,
        "call_gex": call_gex,
        "put_gex": put_gex,
        "call_oi": [round(per_strike[k][2]) for k in strikes],
        "put_oi": [round(per_strike[k][3]) for k in strikes],
        "call_vol": [round(per_strike[k][4]) for k in strikes],
        "put_vol": [round(per_strike[k][5]) for k in strikes],
        "call_dex": [round(per_strike[k][6], 3) for k in strikes],
        "put_dex": [round(per_strike[k][7], 3) for k in strikes],
        "per_expiration": {k: round(v, 3) for k, v in sorted(per_exp.items())},
        "summary": {
            "net_gex": round(sum(net), 3),
            "net_dex": round(sum(per_strike[k][6] + per_strike[k][7] for k in strikes), 3),
            "flip": flip,
            "call_wall": call_wall,
            "put_wall": put_wall,
        },
    }


def market_open(now_ny: datetime) -> bool:
    if now_ny.weekday() >= 5:
        return False
    hm = now_ny.hour * 60 + now_ny.minute
    return 9 * 60 + 20 <= hm <= 16 * 60 + 25


def save(sym: str, snap: dict, force: bool) -> bool:
    day_dir = OUT / sym / snap["day"]
    day_file = day_dir / "day.json"
    day = {"day": snap["day"], "symbol": sym, "snapshots": []}
    if day_file.exists():
        day = json.loads(day_file.read_text())

    # Dédoublonnage : données CBOE inchangées depuis le dernier snapshot
    if not force and day["snapshots"]:
        last = day["snapshots"][-1]
        if last.get("cboe_timestamp") == snap["cboe_timestamp"]:
            print(f"[{sym}] données inchangées ({snap['cboe_timestamp']}), snapshot ignoré")
            return False

    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / f"{snap['time']}.json").write_text(
        json.dumps(snap, separators=(",", ":")), encoding="utf-8"
    )
    entry = {
        "time": snap["time"],
        "file": f"{snap['time']}.json",
        "spot": snap["spot"],
        "cboe_timestamp": snap["cboe_timestamp"],
        **snap["summary"],
    }
    day["snapshots"] = [s for s in day["snapshots"] if s["time"] != snap["time"]] + [entry]
    day["snapshots"].sort(key=lambda s: s["time"])
    day_file.write_text(json.dumps(day, indent=1), encoding="utf-8")

    days_file = OUT / sym / "days.json"
    days = json.loads(days_file.read_text()) if days_file.exists() else {"symbol": sym, "days": []}
    if snap["day"] not in days["days"]:
        days["days"].append(snap["day"])
        days["days"].sort()
    days_file.write_text(json.dumps(days, indent=1), encoding="utf-8")
    print(f"[{sym}] snapshot {snap['day']} {snap['time']} NY — spot {snap['spot']}, "
          f"net GEX {snap['summary']['net_gex']}M$, flip {snap['summary']['flip']}")
    return True


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    force = "--force" in sys.argv
    syms = args or list(SYMBOLS)
    now_ny = datetime.now(NY)

    if not force and not market_open(now_ny):
        print(f"Marché fermé ({now_ny:%Y-%m-%d %H:%M} NY) — rien à faire (utiliser --force pour ignorer)")
        return 0

    wrote = False
    latest = {}
    for sym in syms:
        cfg = SYMBOLS.get(sym)
        if not cfg:
            print(f"Symbole inconnu : {sym} (disponibles : {', '.join(SYMBOLS)})", file=sys.stderr)
            continue
        try:
            raw = fetch(cfg["cboe"])
        except Exception as e:  # noqa: BLE001 — un symbole en échec ne bloque pas les autres
            print(f"[{sym}] échec de récupération CBOE : {e}", file=sys.stderr)
            continue
        snap = build_snapshot(sym, cfg, raw, now_ny)
        if save(sym, snap, force):
            wrote = True
        latest[sym] = snap["day"]

    manifest_file = OUT / "manifest.json"
    manifest = json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
    manifest.setdefault("symbols", sorted(SYMBOLS))
    manifest["symbols"] = sorted(set(manifest["symbols"]) | set(SYMBOLS))
    manifest.setdefault("latest_day", {}).update(latest)
    manifest["updated"] = now_ny.isoformat(timespec="seconds")
    if wrote or not manifest_file.exists():
        OUT.mkdir(parents=True, exist_ok=True)
        manifest_file.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
