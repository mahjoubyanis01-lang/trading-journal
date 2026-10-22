"""Agrégation des facteurs en score directionnel [-100, +100], biais et confiance.

- Score = somme des contributions des facteurs, renormalisée sur la somme des
  poids DISPONIBLES puis bornée à ±100. Un facteur manquant ne tire pas le
  score vers zéro artificiellement, mais il réduit la confiance.
- Biais : seuils configurables (défaut ±25) — valeurs initiales, pas des
  seuils réputés optimaux.
- Confiance [0, 100] : combinaison de la complétude des données, du nombre de
  facteurs disponibles et de la cohérence (accord) entre facteurs. Ce n'est
  PAS une probabilité de réussite calibrée.
- Données insuffisantes => « NEUTRE — données insuffisantes ».
"""
from __future__ import annotations

from .factors import Factor

MIN_FACTORS_FOR_CALL = 3
MIN_WEIGHT_COVERAGE = 0.35  # part minimale du poids total couverte par des données


def aggregate(factors: list[Factor], bullish_threshold: float, bearish_threshold: float) -> dict:
    total_weight = sum(f.weight for f in factors) or 1.0
    avail = [f for f in factors if f.available]
    avail_weight = sum(f.weight for f in avail)
    raw = sum(f.score for f in avail)

    # Renormalisation : le score exprime la direction sur les facteurs observés.
    coverage = avail_weight / total_weight
    score = 0.0
    if avail_weight > 0:
        score = max(-100.0, min(100.0, raw / avail_weight * 100.0))

    # Cohérence : |somme| / somme des |contributions| (1 = tous d'accord).
    abs_sum = sum(abs(f.score) for f in avail)
    agreement = abs(raw) / abs_sum if abs_sum > 1e-9 else 0.0

    insufficient = len(avail) < MIN_FACTORS_FOR_CALL or coverage < MIN_WEIGHT_COVERAGE

    confidence = round(100 * (0.45 * coverage + 0.25 * min(len(avail) / 8, 1.0)
                              + 0.30 * agreement))
    confidence = max(0, min(100, confidence))

    if insufficient:
        bias, reason = "neutral", "données insuffisantes"
    elif score >= bullish_threshold:
        bias, reason = "bullish", "score au-dessus du seuil haussier"
    elif score <= bearish_threshold:
        bias, reason = "bearish", "score au-dessous du seuil baissier"
    else:
        bias, reason = "neutral", "signaux sans avantage directionnel suffisant"

    return {
        "score": round(score, 1),
        "bias": bias,
        "bias_reason": reason,
        "confidence": confidence,
        "coverage": round(coverage * 100, 1),
        "agreement": round(agreement, 3),
        "insufficient": insufficient,
        "n_factors_available": len(avail),
    }


def build_reasoning(factors: list[Factor], agg: dict, bullish_threshold: float,
                    bearish_threshold: float) -> dict:
    bullish = [f"{f.label} : {f.value} — {f.rationale}" for f in factors
               if f.available and f.score > 1]
    bearish = [f"{f.label} : {f.value} — {f.rationale}" for f in factors
               if f.available and f.score < -1]
    neutral = [f"{f.label} : {f.value}" for f in factors if f.available and -1 <= f.score <= 1]
    missing = [f.label for f in factors if not f.available]

    contradictions = []
    if bullish and bearish:
        contradictions.append(
            f"{len(bullish)} facteur(s) haussier(s) contre {len(bearish)} baissier(s) : "
            f"cohérence {agg['agreement']:.0%}.")

    label = {"bullish": "HAUSSIER", "bearish": "BAISSIER", "neutral": "NEUTRE"}[agg["bias"]]
    if agg["insufficient"]:
        label = "NEUTRE — données insuffisantes"
    text = (f"Score directionnel {agg['score']:+.0f} (seuils {bearish_threshold:+.0f} / "
            f"{bullish_threshold:+.0f}) sur {agg['n_factors_available']} facteurs couvrant "
            f"{agg['coverage']:.0f} % du poids total → biais {label}. ")
    if bullish:
        text += f"Soutiens : {len(bullish)} facteur(s) haussier(s). "
    if bearish:
        text += f"Freins : {len(bearish)} facteur(s) baissier(s). "
    if missing:
        text += f"Facteurs indisponibles : {', '.join(missing)}. "
    text += (f"Confiance {agg['confidence']}/100 — reflète la complétude et la cohérence "
             "des données, pas une probabilité calibrée de réussite.")

    return {"bullish_factors": bullish, "bearish_factors": bearish,
            "neutral_factors": neutral, "contradictions": contradictions,
            "reasoning": text, "missing_factors": missing}
