"""Databento — données ES contrat par contrat (fournisseur PAYANT, optionnel).

Pourquoi : Yahoo ne fournit l'intraday 30 min que ~60 jours en arrière et ne
donne que le contrat continu. Pour un backtest sur 90 ou 252 séances avec de
vraies données de contrat (GLBX.MDP3, CME Globex), Databento est l'intégration
prévue. Elle utilise l'API historique HTTP officielle :
https://databento.com/docs/api-reference-historical

Méthode de continuité : symbole continu ``ES.c.0`` (front month par volume,
stype_in=continuous), SANS ajustement de prix — même convention que Yahoo :
les deux bornes d'une mesure intra-journée proviennent du même contrat, le
champ renvoyé ``symbol`` (ex: ESZ6) identifie le contrat réellement utilisé
pour chaque bougie, ce qui rend les rolls totalement traçables.

Configuration : clé API Databento (db-...) + droits sur le dataset GLBX.MDP3.
Cette intégration est fonctionnelle mais FACTURÉE par Databento à l'usage ;
sans clé valide, le fournisseur signale l'erreur et le backtest utilise Yahoo.
"""
from __future__ import annotations

import json
from datetime import datetime

import httpx

from .base import ProviderError, cached_get
from ..config import get_api_key
from ..providers.yahoo import Bar
from ..timeutil import UTC

API = "https://hist.databento.com/v0"


def _key() -> str:
    key = get_api_key("databento")
    if not key:
        raise ProviderError("Databento non configuré (clé API absente)")
    return key


def get_bars(start_utc: datetime, end_utc: datetime) -> list[Bar]:
    """Bougies 1 minute ES continu (front month) sur [start, end), en UTC."""
    key = _key()
    params = {
        "dataset": "GLBX.MDP3",
        "symbols": "ES.c.0",
        "stype_in": "continuous",
        "schema": "ohlcv-1m",
        "start": start_utc.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
        "end": end_utc.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
        "encoding": "json",
        "pretty_px": "true",
        "map_symbols": "true",
    }
    body = cached_get(
        f"{API}/timeseries.get_range", params,
        cache_namespace="databento:es",
        cache_key_params={k: v for k, v in params.items()},
        min_interval=1.0, timeout=120,
        headers={"Authorization": "Basic " + _basic(key)},
    )
    bars: list[Bar] = []
    for line in body.decode().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        hd = rec.get("hd", rec)
        ts_event = int(hd.get("ts_event", 0))
        start = datetime.fromtimestamp(ts_event / 1e9, tz=UTC)
        try:
            o, h, l, c = (float(rec["open"]), float(rec["high"]),
                          float(rec["low"]), float(rec["close"]))
        except (KeyError, ValueError):
            continue
        from datetime import timedelta
        bars.append(Bar(start, start + timedelta(minutes=1), o, h, l, c, rec.get("volume")))
    if not bars:
        raise ProviderError("Databento : aucune bougie renvoyée sur la fenêtre demandée")
    return bars


def _basic(key: str) -> str:
    import base64
    return base64.b64encode(f"{key}:".encode()).decode()


def test_connection() -> tuple[bool, str]:
    try:
        key = get_api_key("databento")
        if not key:
            return False, "Clé API Databento non configurée"
        r = httpx.get(f"{API}/metadata.list_datasets", timeout=30,
                      headers={"Authorization": "Basic " + _basic(key)})
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}: {r.text[:150]}"
        datasets = r.json()
        ok = "GLBX.MDP3" in datasets
        return ok, ("OK — accès GLBX.MDP3 (CME Globex)" if ok
                    else "Clé valide mais pas d'accès au dataset GLBX.MDP3 (CME)")
    except Exception as e:  # noqa: BLE001
        return False, str(e)
