"""Analyse de sentiment HEURISTIQUE des titres de presse (lexique transparent).

Il s'agit d'un classement par mots-clés, documenté et reproductible — pas d'un
modèle calibré. Chaque titre reçoit : positif / négatif / neutre pour les
actions US, plus des marqueurs spécifiques (risque géopolitique, faucon/colombe
monétaire). Les limites de cette approche sont signalées dans chaque séance.
"""
from __future__ import annotations

import re

# Termes orientés « risk-on » / favorables aux actions US.
POSITIVE = {
    "rally", "rallies", "surge", "surges", "soar", "soars", "jump", "jumps",
    "record high", "beats", "beat estimates", "tops estimates", "strong results",
    "rate cut", "rate cuts", "dovish", "easing", "stimulus", "ceasefire",
    "truce", "deal reached", "agreement", "tariff relief", "tariffs lifted",
    "cooling inflation", "inflation cools", "inflation slows", "soft landing",
    "upgrade", "upgraded", "raises guidance", "raises outlook", "optimism",
    "rebound", "rebounds", "recovery", "gains",
}

# Termes orientés « risk-off » / défavorables aux actions US.
NEGATIVE = {
    "plunge", "plunges", "tumble", "tumbles", "sink", "sinks", "slump", "slumps",
    "selloff", "sell-off", "crash", "misses", "miss estimates", "weak results",
    "profit warning", "cuts guidance", "lowers outlook", "recession", "contraction",
    "rate hike", "rate hikes", "hawkish", "tightening", "sticky inflation",
    "inflation accelerates", "hot inflation", "stagflation", "default",
    "government shutdown", "downgrade", "downgraded", "layoffs", "bankruptcy",
    "credit crunch", "banking crisis", "liquidity crisis", "escalation",
    "escalates", "attack", "attacks", "strikes", "invasion", "sanctions",
    "tariff", "tariffs", "trade war", "retaliation", "missile", "warning",
    "fears", "turmoil", "crisis", "losses",
}

# Marqueurs de risque géopolitique (pèsent asymétriquement : aversion au risque).
GEOPOLITICAL_RISK = {
    "war", "invasion", "missile", "strike", "strikes", "attack", "attacks",
    "escalation", "escalates", "sanctions", "embargo", "blockade", "tariff",
    "tariffs", "trade war", "retaliation", "nuclear", "troops", "conflict",
    "opec cut", "supply disruption", "pipeline", "strait of hormuz",
}
GEOPOLITICAL_RELIEF = {"ceasefire", "truce", "peace deal", "de-escalation",
                       "deal reached", "tariff relief", "talks resume"}

_word_re = re.compile(r"[a-z][a-z\-']*")


def _matches(text: str, vocab: set[str]) -> list[str]:
    found = []
    for term in vocab:
        if " " in term or "-" in term:
            if term in text:
                found.append(term)
        else:
            if re.search(rf"\b{re.escape(term)}\b", text):
                found.append(term)
    return found


def classify_title(title: str) -> dict:
    """Retourne sentiment ('positive'|'negative'|'neutral'), score [-1..1],
    et marqueurs géopolitiques trouvés."""
    text = title.lower()
    pos = _matches(text, POSITIVE)
    neg = _matches(text, NEGATIVE)
    geo_risk = _matches(text, GEOPOLITICAL_RISK)
    geo_relief = _matches(text, GEOPOLITICAL_RELIEF)
    raw = len(pos) - len(neg)
    if raw > 0:
        sentiment, score = "positive", min(1.0, raw / 2)
    elif raw < 0:
        sentiment, score = "negative", max(-1.0, raw / 2)
    else:
        sentiment, score = "neutral", 0.0
    return {
        "sentiment": sentiment, "score": score,
        "positive_terms": pos, "negative_terms": neg,
        "geo_risk_terms": geo_risk, "geo_relief_terms": geo_relief,
    }
