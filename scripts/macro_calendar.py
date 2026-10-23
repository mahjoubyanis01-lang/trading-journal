#!/usr/bin/env python3
"""Calendrier macro US (annonces à impact fort / moyen) pour le plan du jour.

Source : flux public ForexFactory (semaine en cours + semaine suivante).
Sortie : data/macro/calendar.json  {"updated":..., "events":[{date,time,title,impact,forecast,previous}]}
Usage  : python3 scripts/macro_calendar.py
"""
import json
import ssl
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "macro" / "calendar.json"
FEEDS = (
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
)
# Annonces qui font réellement bouger les indices US (impact « High » du flux,
# plus quelques « Medium » suivies par les traders de futures)
WATCH_MEDIUM = ("ISM", "PMI", "Retail Sales", "Unemployment Claims", "JOLTS", "Consumer Sentiment", "PCE", "GDP")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as r:
        return json.load(r)


def update() -> dict:
    events = {}
    if OUT.exists():
        for e in json.loads(OUT.read_text()).get("events", []):
            events[(e["date"], e["time"], e["title"])] = e
    for url in FEEDS:
        try:
            feed = fetch(url)
        except Exception as e:  # noqa: BLE001 — la semaine suivante n'est publiée qu'en fin de semaine
            print(f"calendrier indisponible ({url.rsplit('/', 1)[-1]}) : {e}", file=sys.stderr)
            continue
        for e in feed:
            if e.get("country") != "USD":
                continue
            imp = e.get("impact")
            if imp != "High" and not (imp == "Medium" and any(w in e["title"] for w in WATCH_MEDIUM)):
                continue
            t = datetime.fromisoformat(e["date"]).astimezone(NY)
            ev = {
                "date": t.date().isoformat(),
                "time": t.strftime("%H:%M"),
                "title": e["title"],
                "impact": "fort" if imp == "High" else "moyen",
                "forecast": e.get("forecast") or "",
                "previous": e.get("previous") or "",
            }
            events[(ev["date"], ev["time"], ev["title"])] = ev
    out = {
        "updated": datetime.now(NY).isoformat(timespec="seconds"),
        "source": "ForexFactory (flux public), heures de New York",
        "events": sorted(events.values(), key=lambda e: (e["date"], e["time"])),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def events_for(day: str) -> list:
    if not OUT.exists():
        return []
    return [e for e in json.loads(OUT.read_text())["events"] if e["date"] == day]


if __name__ == "__main__":
    o = update()
    for e in o["events"]:
        print(e["date"], e["time"], e["impact"], e["title"], e["forecast"], e["previous"])
