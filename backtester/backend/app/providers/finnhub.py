"""Finnhub — calendrier des résultats d'entreprises (clé API gratuite possible).

Utilisé pour savoir quelles grandes capitalisations du S&P 500 ont publié
leurs résultats AVANT la limite d'information (publication la veille après
clôture « amc », ou le matin même avant ouverture « bmo »), avec surprise BPA
réel vs estimé lorsque Finnhub la fournit.

Limites documentées :
- Le plan gratuit de Finnhub limite le calendrier historique (souvent ~1 an)
  et le débit (60 requêtes/min). En cas de refus (403/429), l'erreur est
  journalisée et la séance continue sans ce facteur.
- L'estimation BPA de Finnhub est un consensus au moment de la collecte, pas
  une archive stricte point-in-time : signalé dans les limites de séance.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .base import ProviderError, get_json
from ..config import get_api_key
from ..timeutil import NEW_YORK

API = "https://finnhub.io/api/v1"

# Poids approximatifs (%) des mégacaps dans le S&P 500 — ordre de grandeur
# utilisé pour pondérer l'importance d'une publication, pas une donnée exacte.
MEGACAP_WEIGHTS = {
    "NVDA": 7.5, "MSFT": 6.5, "AAPL": 6.0, "AMZN": 4.0, "GOOGL": 2.5,
    "GOOG": 2.0, "META": 2.5, "TSLA": 1.8, "AVGO": 2.0, "BRK.B": 1.6,
    "JPM": 1.4, "LLY": 1.3, "V": 1.0, "XOM": 1.0, "UNH": 0.8,
}


def _key() -> str:
    key = get_api_key("finnhub")
    if not key:
        raise ProviderError("Finnhub non configuré (clé API absente)")
    return key


def earnings_before_cutoff(session_date: date, cutoff: datetime) -> list[dict]:
    """Résultats publiés entre la clôture de la veille et la limite du jour.

    Convention d'horodatage : 'amc' (after market close) ≈ 16:30 ET,
    'bmo' (before market open) ≈ 07:30 ET, inconnu => exclu par prudence.
    """
    frm = session_date - timedelta(days=1)
    data = get_json(
        f"{API}/calendar/earnings",
        {"from": frm.isoformat(), "to": session_date.isoformat(), "token": _key()},
        cache_namespace="finnhub:earnings",
        cache_key_params={"from": frm.isoformat(), "to": session_date.isoformat()},
        min_interval=1.1,
    )
    out = []
    for e in data.get("earningsCalendar", []):
        sym = e.get("symbol", "")
        hour = (e.get("hour") or "").lower()
        d = e.get("date")
        if not d:
            continue
        ed = date.fromisoformat(d)
        if hour == "amc":
            released_at = datetime.combine(ed, time(16, 30), tzinfo=NEW_YORK)
        elif hour == "bmo":
            released_at = datetime.combine(ed, time(7, 30), tzinfo=NEW_YORK)
        else:
            continue
        if not (released_at <= cutoff and released_at >= datetime.combine(
                frm, time(16, 0), tzinfo=NEW_YORK)):
            continue
        actual, estimate = e.get("epsActual"), e.get("epsEstimate")
        surprise = None
        if actual is not None and estimate not in (None, 0):
            surprise = round((actual - estimate) / abs(estimate) * 100, 2)
        out.append({
            "symbol": sym, "released_at": released_at.isoformat(), "when": hour,
            "eps_actual": actual, "eps_estimate": estimate, "surprise_pct": surprise,
            "revenue_actual": e.get("revenueActual"), "revenue_estimate": e.get("revenueEstimate"),
            "index_weight_pct": MEGACAP_WEIGHTS.get(sym, 0.1),
        })
    out.sort(key=lambda x: x["index_weight_pct"], reverse=True)
    return out[:25]


def test_connection() -> tuple[bool, str]:
    try:
        key = get_api_key("finnhub")
        if not key:
            return False, "Clé API Finnhub non configurée"
        data = get_json(
            f"{API}/quote", {"symbol": "AAPL", "token": key},
            cache_namespace="finnhub:test", cache_key_params={"t": "test"}, max_age_seconds=60,
        )
        if "c" not in data:
            return False, f"réponse inattendue: {str(data)[:120]}"
        return True, f"OK — AAPL dernier cours {data['c']}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)
