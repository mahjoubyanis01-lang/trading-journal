"""GDELT DOC 2.0 — archives d'actualités mondiales, gratuites, horodatées.

Chaque article porte un ``seendate`` (UTC) : on ne retient que les articles
vus AVANT la limite de 15:29 Paris. GDELT couvre la presse en continu depuis
2015, ce qui permet une vraie reconstruction point-in-time des titres.

Limites documentées :
- ``seendate`` est l'heure de découverte par GDELT (granularité 15 min),
  proche mais pas strictement égale à l'heure de publication par le média.
- Le texte intégral n'est pas fourni : l'analyse porte sur les TITRES.
- Quota : 1 requête / 5 s (throttle appliqué, réponses mises en cache).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .base import ProviderError, get_json
from ..timeutil import UTC

API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Domaines de presse économique/générale jugés fiables pour distinguer une
# information confirmée d'une rumeur (liste indicative, extensible).
TRUSTED_DOMAINS = {
    "reuters.com", "bloomberg.com", "cnbc.com", "wsj.com", "ft.com",
    "marketwatch.com", "apnews.com", "finance.yahoo.com", "barrons.com",
    "forbes.com", "businessinsider.com", "theguardian.com", "bbc.com",
    "nytimes.com", "washingtonpost.com", "investing.com", "lesechos.fr",
}

QUERIES = {
    "macro_fed": ('("federal reserve" OR "interest rates" OR inflation OR "jobs report" '
                  'OR CPI OR recession OR "treasury yields" OR "rate cut" OR "rate hike") '
                  'sourcelang:english'),
    "geopolitics": ('(tariffs OR sanctions OR war OR missile OR "trade war" OR OPEC '
                    'OR escalation OR ceasefire OR "oil supply") sourcelang:english'),
    "earnings": ('(Nvidia OR Apple OR Microsoft OR Amazon OR Alphabet OR Meta OR Tesla '
                 'OR "earnings report" OR "quarterly results" OR guidance) sourcelang:english'),
}


def _fmt(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y%m%d%H%M%S")


def fetch_articles(category: str, start: datetime, end: datetime, max_records: int = 60) -> list[dict]:
    query = QUERIES[category]
    params = {
        "query": query, "mode": "artlist", "format": "json",
        "maxrecords": max_records, "sort": "datedesc",
        "startdatetime": _fmt(start), "enddatetime": _fmt(end),
    }
    data = get_json(
        API, params,
        cache_namespace=f"gdelt:{category}",
        min_interval=5.2,  # quota officiel GDELT : 1 req / 5 s
        timeout=45,
    )
    articles = []
    seen_titles: set[str] = set()
    for a in data.get("articles", []):
        title = (a.get("title") or "").strip()
        if not title or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())
        seen = a.get("seendate")  # format 20261021T143000Z
        published_at = None
        if seen:
            try:
                published_at = datetime.strptime(seen, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
            except ValueError:
                published_at = None
        if published_at is not None and not (start <= published_at <= end):
            continue  # ceinture et bretelles : jamais d'article hors fenêtre
        if published_at is None:
            continue  # sans horodatage, impossible de garantir l'absence de fuite
        domain = (a.get("domain") or "").lower()
        articles.append({
            "title": title,
            "source": domain,
            "url": a.get("url"),
            "published_at": published_at.isoformat(),
            "trusted": domain in TRUSTED_DOMAINS,
            "category": category,
            "language": a.get("language"),
        })
    return articles


def fetch_window(start: datetime, end: datetime) -> dict[str, list[dict]]:
    if end - start > timedelta(days=4):
        raise ProviderError("fenêtre GDELT trop large")
    return {cat: fetch_articles(cat, start, end) for cat in QUERIES}


def test_connection() -> tuple[bool, str]:
    try:
        end = datetime.now(UTC) - timedelta(hours=1)
        arts = fetch_articles("macro_fed", end - timedelta(hours=12), end, max_records=5)
        return True, f"OK — {len(arts)} articles de test récupérés"
    except Exception as e:  # noqa: BLE001
        return False, str(e)
