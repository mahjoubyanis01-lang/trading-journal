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

# Disjoncteur par domaine : après plusieurs épuisements de quota (429)
# consécutifs, on ne fait plus qu'une tentative par requête au lieu de
# retries longs — le cache local reste utilisé et un succès réarme tout.
_domain_429_failures: dict[str, int] = {}
_BREAKER_THRESHOLD = 3

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
        breaker_open = _domain_429_failures.get(domain, 0) >= _BREAKER_THRESHOLD
        max_429_attempts = 1 if breaker_open else 6
        if resp.status_code == 429 and attempts < max_429_attempts:
            time_mod.sleep(8 * attempts)
            continue
        if resp.status_code != 200:
            if resp.status_code == 429:
                _domain_429_failures[domain] = _domain_429_failures.get(domain, 0) + 1
                suffix = (" — quota dépassé de façon répétée, tentatives réduites "
                          "pour le reste de l'exécution" if breaker_open else "")
                raise ProviderError(f"{domain} HTTP 429 (quota){suffix}")
            raise ProviderError(f"{domain} HTTP {resp.status_code}: {resp.text[:200]}")
        _domain_429_failures[domain] = 0
        db.cache_put(cache_key, str(httpx.URL(url).copy_merge_params(key_params)), 200, resp.content)
        return resp.content


def get_json(url: str, params: dict | None = None, **kw) -> dict:
    body = cached_get(url, params, **kw)
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise ProviderError(f"réponse non-JSON de {url[:80]}") from e
