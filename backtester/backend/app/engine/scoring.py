"""Agrégation des facteurs en score directionnel [-100, +100], biais et confiance.

- Score = somme des contributions des facteurs, renormalisée sur la somme des
  poids DISPONIBLES puis bornée à ±100. Un facteur manquant ne tire pas le
  score vers zéro artificiellement, mais il réduit la confiance.
- Biais tranché en CINQ niveaux : hausse affirmée (score >= seuil fort,
  défaut +55), hausse modérée (>= +25), neutre, baisse modérée (<= -25),
  baisse affirmée (<= -55). Seuils configurables — valeurs initiales, pas
  des seuils réputés optimaux.
- Confiance [0, 100] : combinaison de la complétude des données, du nombre de
  facteurs disponibles et de la cohérence (accord) entre facteurs. Ce n'est
  PAS une probabilité de réussite calibrée.
- Données insuffisantes => « NEUTRE — données insuffisantes ».
"""
from __future__ import annotations

from .factors import Factor

MIN_FACTORS_FOR_CALL = 3
MIN_WEIGHT_COVERAGE = 0.35  # part minimale du poids total couverte par des données


BIAS_LABELS_FR = {
    "strong_bullish": "HAUSSE AFFIRMÉE",
    "bullish": "HAUSSE MODÉRÉE",
    "neutral": "NEUTRE",
    "bearish": "BAISSE MODÉRÉE",
    "strong_bearish": "BAISSE AFFIRMÉE",
}


def aggregate(factors: list[Factor], bullish_threshold: float, bearish_threshold: float,
              strong_bullish_threshold: float = 55.0,
              strong_bearish_threshold: float = -55.0) -> dict:
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
    elif score >= strong_bullish_threshold:
        bias, reason = "strong_bullish", "score au-dessus du seuil haussier fort"
    elif score >= bullish_threshold:
        bias, reason = "bullish", "score au-dessus du seuil haussier modéré"
    elif score <= strong_bearish_threshold:
        bias, reason = "strong_bearish", "score au-dessous du seuil baissier fort"
    elif score <= bearish_threshold:
        bias, reason = "bearish", "score au-dessous du seuil baissier modéré"
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
                    bearish_threshold: float,
                    strong_bullish_threshold: float = 55.0,
                    strong_bearish_threshold: float = -55.0) -> dict:
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

    label = BIAS_LABELS_FR[agg["bias"]]
    if agg["insufficient"]:
        label = "NEUTRE — données insuffisantes"
    text = (f"Score directionnel {agg['score']:+.0f} (seuils modérés "
            f"{bearish_threshold:+.0f} / {bullish_threshold:+.0f}, affirmés "
            f"{strong_bearish_threshold:+.0f} / {strong_bullish_threshold:+.0f}) sur "
            f"{agg['n_factors_available']} facteurs couvrant "
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
