"""Verdict du jour en temps réel, calculé par le moteur complet.

- Avant l'heure limite : verdict PROVISOIRE sur les données <= maintenant.
- Après : verdict FIGÉ sur les données <= heure limite (même méthode que le
  backtest).
- La mesure 9h30 NY -> minuit Paris est renvoyée partielle tant que la séance
  n'est pas terminée.
"""
from __future__ import annotations

import threading
import time as _time
from datetime import datetime

from .backtest.runner import analyze_session
from .config import load_settings
from .timeutil import NEW_YORK, PARIS, cutoff_paris, measure_end_paris

_cache: dict = {}
_lock = threading.Lock()


def compute_live_verdict(refresh: bool = False) -> dict:
    settings = load_settings()
    now_paris = datetime.now(PARIS)
    today = datetime.now(NEW_YORK).date()
    if today.weekday() >= 5:
        return {"available": False,
                "message": "Marché fermé (week-end) : pas de verdict du jour."}

    cutoff = cutoff_paris(today, settings["cutoff_paris"])
    provisional = now_paris < cutoff
    cache_key = (today.isoformat(), provisional)
    with _lock:
        cached = _cache.get("payload")
        if (not refresh and cached is not None
                and _cache.get("key") == cache_key
                and _time.time() - _cache.get("at", 0) < 120):
            return cached

    live_settings = dict(settings)
    if provisional:
        live_settings["cutoff_paris"] = now_paris.strftime("%H:%M")

    # Séance précédente (pour la fenêtre d'actualités).
    try:
        from .providers.yahoo import get_trading_sessions
        prev = get_trading_sessions(1)[-1]
    except Exception:  # noqa: BLE001
        prev = None

    try:
        result = analyze_session(today, live_settings, prev)
    except Exception as e:  # noqa: BLE001
        return {"available": False,
                "message": f"Analyse impossible (marché fermé ou données "
                           f"indisponibles) : {e}"}

    end = measure_end_paris(today)
    in_progress = now_paris < end
    result["live"] = True
    result["provisional"] = provisional
    result["as_of"] = now_paris.isoformat()
    if in_progress:
        result["measurement"]["in_progress"] = True
        result["measurement"]["note"] = ("Séance en cours : mesure partielle "
                                         "jusqu'au dernier prix disponible, "
                                         "résultat définitif à minuit (Paris).")
        # Pas de « correct/exact » définitifs sur une séance inachevée.
        result["measurement"]["correct"] = None
        result["measurement"]["exact"] = None
    payload = {"available": True, "session": result}
    with _lock:
        _cache.update({"key": cache_key, "at": _time.time(), "payload": payload})
    return payload
