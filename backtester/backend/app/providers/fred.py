"""FRED / ALFRED — séries macroéconomiques américaines POINT-IN-TIME.

ALFRED (realtime_start/realtime_end) renvoie les valeurs telles qu'elles
étaient CONNUES à une date donnée : les révisions ultérieures ne sont jamais
utilisées comme si elles avaient été publiées initialement.

Limites documentées :
- FRED ne fournit PAS le consensus des économistes : la « surprise » est
  calculée par rapport à la valeur précédente connue, et le champ
  ``consensus_available`` reste à False.
- FRED fournit les dates de publication (release dates) mais pas l'heure.
  L'heure est déduite du créneau de publication officiel et stable de chaque
  statistique (BLS/BEA/Census : 08:30 ET ; Fed G.17 etc. : voir tableau).
  Les publications à 10:00 ET et plus tard tombent APRÈS la limite de 15:29
  Paris les jours où le décalage Paris–NY est de 6 h ou moins : elles ne sont
  alors utilisables que le lendemain. Le filtrage est fait sur l'horodatage
  reconstruit, jamais sur la seule date.

Clé API gratuite requise : https://fred.stlouisfed.org/docs/api/api_key.html
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .base import ProviderError, get_json
from ..config import get_api_key
from ..timeutil import NEW_YORK

API = "https://api.stlouisfed.org/fred"

# series_id -> (nom, release_id FRED, heure de publication ET, unité, higher_is)
# higher_is : interprétation de principe pour les actions US d'une valeur
# supérieure aux attentes — "hawkish" (pèse via les taux), "growth" (soutient),
# "mixed" (dépend du régime). L'interprétation finale est faite dans le moteur.
SERIES: dict[str, dict] = {
    "CPIAUCSL":  {"name": "CPI (inflation, indice)", "release_hour": time(8, 30), "unit": "index", "kind": "inflation", "pct_change": True},
    "CPILFESL":  {"name": "Core CPI (indice)", "release_hour": time(8, 30), "unit": "index", "kind": "inflation", "pct_change": True},
    "PCEPILFE":  {"name": "Core PCE (indice)", "release_hour": time(8, 30), "unit": "index", "kind": "inflation", "pct_change": True},
    "PAYEMS":    {"name": "Emplois non agricoles (NFP, milliers)", "release_hour": time(8, 30), "unit": "k", "kind": "growth", "diff": True},
    "UNRATE":    {"name": "Taux de chômage (%)", "release_hour": time(8, 30), "unit": "%", "kind": "unemployment"},
    "ICSA":      {"name": "Inscriptions hebdo au chômage (milliers)", "release_hour": time(8, 30), "unit": "k", "kind": "claims"},
    "RSAFS":     {"name": "Ventes au détail (M$)", "release_hour": time(8, 30), "unit": "M$", "kind": "growth", "pct_change": True},
    "GDPC1":     {"name": "PIB réel (annualisé)", "release_hour": time(8, 30), "unit": "Md$", "kind": "growth", "pct_change": True},
    "UMCSENT":   {"name": "Confiance conso. (U. Michigan)", "release_hour": time(10, 0), "unit": "index", "kind": "sentiment"},
    "DGS2":      {"name": "Rendement US 2 ans (%)", "daily": True, "unit": "%", "kind": "rates"},
    "DGS10":     {"name": "Rendement US 10 ans (%)", "daily": True, "unit": "%", "kind": "rates"},
    "DTWEXBGS":  {"name": "Dollar pondéré (broad)", "daily": True, "unit": "index", "kind": "dollar"},
}


def _key() -> str:
    key = get_api_key("fred")
    if not key:
        raise ProviderError("FRED non configuré (clé API absente)")
    return key


def _observations(series_id: str, realtime: date, obs_start: date) -> list[dict]:
    data = get_json(
        f"{API}/series/observations",
        {"series_id": series_id, "api_key": _key(), "file_type": "json",
         "realtime_start": realtime.isoformat(), "realtime_end": realtime.isoformat(),
         "observation_start": obs_start.isoformat(), "sort_order": "desc", "limit": 24},
        cache_namespace=f"fred:obs:{series_id}:{realtime}",
        cache_key_params={"series_id": series_id, "realtime": realtime.isoformat(),
                          "obs_start": obs_start.isoformat()},
        min_interval=0.6,
    )
    return data.get("observations", [])


def _vintage_dates(series_id: str, start: date, end: date) -> list[date]:
    data = get_json(
        f"{API}/series/vintagedates",
        {"series_id": series_id, "api_key": _key(), "file_type": "json",
         "vintage_dates_start": start.isoformat(), "vintage_dates_end": end.isoformat()},
        cache_namespace=f"fred:vint:{series_id}",
        cache_key_params={"series_id": series_id, "start": start.isoformat(), "end": end.isoformat()},
        min_interval=0.6,
    )
    return [date.fromisoformat(d) for d in data.get("vintage_dates", [])]


def releases_before_cutoff(session_date: date, cutoff: datetime) -> list[dict]:
    """Publications macro des ~7 derniers jours, telles que connues au cutoff.

    Pour chaque série mensuelle/hebdo : si une nouvelle vintage (publication)
    est intervenue dans la fenêtre ET que son horodatage reconstruit
    (date de vintage + heure officielle ET) est <= cutoff, on la rapporte
    avec la valeur publiée CE JOUR-LÀ et la valeur précédente telle qu'elle
    était connue la veille de la publication (point-in-time).
    """
    out: list[dict] = []
    window_start = session_date - timedelta(days=7)
    for sid, meta in SERIES.items():
        if meta.get("daily"):
            continue
        try:
            vintages = _vintage_dates(sid, window_start, session_date)
        except ProviderError:
            raise
        for vd in vintages:
            released_at = datetime.combine(vd, meta["release_hour"], tzinfo=NEW_YORK)
            if not (window_start <= vd <= session_date) or released_at > cutoff:
                continue
            obs_new = _observations(sid, vd, vd - timedelta(days=500))
            obs_old = _observations(sid, vd - timedelta(days=1), vd - timedelta(days=500))
            if not obs_new:
                continue
            latest = obs_new[0]
            prev_known = obs_old[0] if obs_old else None
            try:
                value = float(latest["value"])
            except (ValueError, KeyError):
                continue
            previous = None
            if prev_known:
                try:
                    previous = float(prev_known["value"])
                except (ValueError, KeyError):
                    previous = None
            entry = {
                "series": sid, "name": meta["name"], "period": latest.get("date"),
                "released_at": released_at.isoformat(), "value": value,
                "previous": previous, "consensus": None, "consensus_available": False,
                "kind": meta["kind"], "unit": meta["unit"],
            }
            if meta.get("pct_change") and previous:
                entry["change_pct"] = round((value - previous) / previous * 100, 3)
            if meta.get("diff") and previous is not None:
                entry["change"] = round(value - previous, 3)
            if previous is not None:
                entry["surprise_vs_previous"] = round(value - previous, 4)
            out.append(entry)
    out.sort(key=lambda e: e["released_at"], reverse=True)
    return out


def daily_series_asof(series_id: str, session_date: date) -> list[tuple[date, float]]:
    """Valeurs quotidiennes (taux, dollar) connues au matin de la séance :
    on interroge la vintage de la VEILLE pour exclure toute valeur du jour,
    les séries quotidiennes H.15 étant publiées l'après-midi (heure US),
    c'est-à-dire après 15:29 Paris. Renvoie les ~15 derniers points connus."""
    realtime = session_date - timedelta(days=1)
    obs = _observations(series_id, realtime, session_date - timedelta(days=40))
    out: list[tuple[date, float]] = []
    for o in obs:
        try:
            out.append((date.fromisoformat(o["date"]), float(o["value"])))
        except (ValueError, KeyError):
            continue
    out.sort(key=lambda t: t[0])
    return out[-15:]


def test_connection() -> tuple[bool, str]:
    try:
        key = get_api_key("fred")
        if not key:
            return False, "Clé API FRED non configurée"
        data = get_json(
            f"{API}/series", {"series_id": "CPIAUCSL", "api_key": key, "file_type": "json"},
            cache_namespace="fred:test", cache_key_params={"t": "test"}, max_age_seconds=60,
        )
        title = (data.get("seriess") or [{}])[0].get("title", "?")
        return True, f"OK — accès à « {title} »"
    except Exception as e:  # noqa: BLE001
        return False, str(e)
