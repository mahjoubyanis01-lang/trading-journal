"""Gestion des fuseaux horaires Paris / New York.

Le décalage Paris–New York n'est PAS supposé constant : chaque instant est
construit dans son fuseau IANA (Europe/Paris, America/New_York) via zoneinfo,
ce qui gère automatiquement les changements d'heure des deux côtés (y compris
les semaines où le décalage vaut 5 h ou 7 h au lieu de 6 h).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
NEW_YORK = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def cutoff_paris(session_date: date, hhmm: str = "15:29") -> datetime:
    """Heure limite d'information : HH:MM heure de Paris, le jour de séance."""
    return datetime.combine(session_date, parse_hhmm(hhmm), tzinfo=PARIS)


def measure_start_ny(session_date: date, hhmm: str = "09:30") -> datetime:
    """Début de mesure : HH:MM heure de New York (ouverture séance régulière)."""
    return datetime.combine(session_date, parse_hhmm(hhmm), tzinfo=NEW_YORK)


def measure_end_paris(session_date: date) -> datetime:
    """Fin de mesure : minuit heure de Paris, au changement de date
    (c'est-à-dire 00:00 Paris du jour calendaire suivant)."""
    return datetime.combine(session_date + timedelta(days=1), time(0, 0), tzinfo=PARIS)


def to_utc(dt: datetime) -> datetime:
    return dt.astimezone(UTC)


def from_unix(ts: int | float, tz: ZoneInfo = UTC) -> datetime:
    return datetime.fromtimestamp(ts, tz=tz)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None
