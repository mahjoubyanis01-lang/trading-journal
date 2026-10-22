"""Socle commun des fournisseurs : requêtes HTTP avec cache SQLite et throttle.

Chaque réponse est mise en cache avec son URL et son heure de collecte, ce qui
évite les requêtes répétées et rend les backtests reproductibles hors ligne.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time as time_mod

import httpx

from .. import db

log = logging.getLogger("backtester.providers")

_throttle_lock = threading.Lock()
_last_call: dict[str, float] = {}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) macro-bias-backtester/0.1"


class ProviderError(Exception):
    """Erreur de collecte auprès d'un fournisseur (réseau, quota, format)."""


def _throttle(domain: str, min_interval: float) -> None:
    with _throttle_lock:
        last = _last_call.get(domain, 0.0)
        wait = last + min_interval - time_mod.monotonic()
        if wait > 0:
            time_mod.sleep(wait)
        _last_call[domain] = time_mod.monotonic()


def cached_get(
    url: str,
    params: dict | None = None,
    *,
    cache_namespace: str,
    max_age_seconds: int | None = None,
    min_interval: float = 0.5,
    timeout: float = 30.0,
    headers: dict | None = None,
    cache_key_params: dict | None = None,
) -> bytes:
    """GET avec cache. ``cache_key_params`` permet d'exclure les secrets
    (clés API) de la clé de cache."""
    key_params = cache_key_params if cache_key_params is not None else (params or {})
    raw = url + "?" + json.dumps(key_params, sort_keys=True)
    cache_key = cache_namespace + ":" + hashlib.sha256(raw.encode()).hexdigest()

    body = db.cache_get(cache_key, max_age_seconds)
    if body is not None:
        return body

    domain = httpx.URL(url).host or url
    attempts = 0
    while True:
        attempts += 1
        _throttle(domain, min_interval)
        try:
            resp = httpx.get(
                url, params=params, timeout=timeout, follow_redirects=True,
                headers={"User-Agent": USER_AGENT, **(headers or {})},
            )
        except httpx.HTTPError as e:
            if attempts < 3:
                time_mod.sleep(2 * attempts)
                continue
            raise ProviderError(f"erreur réseau {domain}: {e}") from e
        if resp.status_code == 429 and attempts < 6:
            time_mod.sleep(8 * attempts)
            continue
        if resp.status_code != 200:
            raise ProviderError(f"{domain} HTTP {resp.status_code}: {resp.text[:200]}")
        db.cache_put(cache_key, str(httpx.URL(url).copy_merge_params(key_params)), 200, resp.content)
        return resp.content


def get_json(url: str, params: dict | None = None, **kw) -> dict:
    body = cached_get(url, params, **kw)
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise ProviderError(f"réponse non-JSON de {url[:80]}") from e
