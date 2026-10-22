"""Évaluation des performances du moteur + références simples (baselines).

Avertissement intégré : sur ~30 séances les résultats sont EXPLORATOIRES ;
le taux de réussite directionnelle n'est pas une preuve de rentabilité (il
faudrait un backtest de trading distinct avec frais, spread et glissement).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from .backtest.measurement import DIRECTION_OF

CATS = ["strong_bullish", "bullish", "neutral", "bearish", "strong_bearish"]

DISCLAIMER = (
    "Résultats exploratoires : avec un échantillon de quelques dizaines de séances, "
    "aucun de ces chiffres n'a de signification statistique robuste. Le taux de "
    "réussite directionnelle mesure la justesse de classement sur l'intervalle "
    "9h30 New York → minuit Paris ; il ne constitue pas une preuve de rentabilité "
    "(une stratégie réelle exigerait un backtest de trading distinct avec règles "
    "d'entrée/sortie, frais, spread et glissement). Les seuils utilisés sont des "
    "paramètres initiaux, pas des seuils optimisés puis validés sur données "
    "indépendantes.")


def _hit_rate(pairs: list[tuple[str, str]]) -> float | None:
    """Taux de justesse DIRECTIONNELLE (hausse/baisse/neutre, intensité ignorée)."""
    if not pairs:
        return None
    return round(sum(1 for p, a in pairs if DIRECTION_OF[p] == DIRECTION_OF[a])
                 / len(pairs), 4)


def _exact_rate(pairs: list[tuple[str, str]]) -> float | None:
    """Taux de classe EXACTE parmi les cinq niveaux."""
    if not pairs:
        return None
    return round(sum(1 for p, a in pairs if p == a) / len(pairs), 4)


def _classify_pre(move_pct: float | None, band: float, strong_band: float = 0.50) -> str | None:
    if move_pct is None:
        return None
    if move_pct > strong_band:
        return "strong_bullish"
    if move_pct > band:
        return "bullish"
    if move_pct < -strong_band:
        return "strong_bearish"
    if move_pct < -band:
        return "bearish"
    return "neutral"


def compute_stats(results: list[dict], neutral_band_pct: float,
                  strong_band_pct: float = 0.50) -> dict:
    evaluated = [r for r in results
                 if r["measurement"]["measurable"] and r["measurement"]["actual"]]
    insufficient = [r for r in results if r.get("insufficient")]

    pairs = [(r["predicted"], r["measurement"]["actual"]) for r in evaluated]
    pairs_excl = [(p, a) for (p, a), r in zip(pairs, evaluated)
                  if r["predicted"] != "neutral"]

    by_cat = {}
    for cat in CATS:
        sel = [r for r in evaluated if r["predicted"] == cat]
        changes = [r["measurement"]["change_pct"] for r in sel]
        spairs = [(r["predicted"], r["measurement"]["actual"]) for r in sel]
        by_cat[cat] = {
            "predicted": len(sel),
            "correct": sum(1 for p, a in spairs if DIRECTION_OF[p] == DIRECTION_OF[a]),
            "exact": sum(1 for p, a in spairs if p == a),
            "hit_rate": _hit_rate(spairs),
            "avg_change_pct": round(sum(changes) / len(changes), 3) if changes else None,
        }

    matrix = [[sum(1 for p, a in pairs if p == pr and a == ac) for ac in CATS] for pr in CATS]

    buckets = [("0-33", 0, 33), ("34-66", 34, 66), ("67-100", 67, 100)]
    by_conf = []
    for name, lo, hi in buckets:
        sel = [r for r in evaluated if lo <= r["confidence"] <= hi]
        by_conf.append({"bucket": name, "n": len(sel),
                        "hit_rate": _hit_rate([(r["predicted"], r["measurement"]["actual"])
                                               for r in sel])})

    weekly = defaultdict(lambda: {"n": 0, "correct": 0})
    for r in evaluated:
        y, w, _ = date.fromisoformat(r["date"]).isocalendar()
        key = f"{y}-S{w:02d}"
        weekly[key]["n"] += 1
        weekly[key]["correct"] += 1 if r["measurement"]["correct"] else 0
    by_week = [{"week": k, "n": v["n"], "correct": v["correct"],
                "hit_rate": round(v["correct"] / v["n"], 3)}
               for k, v in sorted(weekly.items())]

    changes = sorted(r["measurement"]["change_pct"] for r in evaluated)
    bins = [(-10, -1), (-1, -0.5), (-0.5, -0.1), (-0.1, 0.1), (0.1, 0.5), (0.5, 1), (1, 10)]
    dist = []
    for lo, hi in bins:
        count = sum(1 for c in changes if lo <= c < hi)
        dist.append({"bin": f"{lo:+.1f} % à {hi:+.1f} %".replace("+-10.0 %", "").strip(),
                     "lo": lo, "hi": hi, "count": count})

    # Références simples, évaluées sur les MÊMES séances mesurables.
    baselines = []
    for bid, label, pred_fn in (
        ("always_up", "Toujours haussier", lambda r: "bullish"),
        ("always_down", "Toujours baissier", lambda r: "bearish"),
        ("follow_preopen", "Suivre le mouvement préouverture du ES",
         lambda r: _classify_pre(r.get("preopen_market", {}).get("es_move_pct"),
                                 neutral_band_pct, strong_band_pct)),
        ("prior_day_momentum", "Momentum : direction de la séance précédente",
         None),
    ):
        if bid == "prior_day_momentum":
            bpairs = []
            for i, r in enumerate(evaluated):
                if i == 0:
                    continue
                prev_actual = evaluated[i - 1]["measurement"]["actual"]
                if prev_actual:
                    bpairs.append((prev_actual, r["measurement"]["actual"]))
        else:
            bpairs = []
            for r in evaluated:
                p = pred_fn(r)
                if p is not None:
                    bpairs.append((p, r["measurement"]["actual"]))
        baselines.append({"id": bid, "label": label, "hit_rate": _hit_rate(bpairs),
                          "n": len(bpairs)})

    # Séparation CHRONOLOGIQUE (jamais aléatoire) : première moitié
    # (« développement » — pour régler les paramètres) vs seconde moitié
    # (« validation » — pour évaluer les choix). Un vrai test final doit se
    # faire sur une période ultérieure jamais utilisée pour ajuster.
    half = len(evaluated) // 2
    split = {}
    for name, part in (("developpement", evaluated[:half]), ("validation", evaluated[half:])):
        ppairs = [(r["predicted"], r["measurement"]["actual"]) for r in part]
        split[name] = {
            "n": len(part), "hit_rate": _hit_rate(ppairs),
            "start": part[0]["date"] if part else None,
            "end": part[-1]["date"] if part else None,
        }

    return {
        "n_sessions": len(results),
        "n_evaluated": len(evaluated),
        "chronological_split": split,
        "n_insufficient": len(insufficient),
        "hit_rate": _hit_rate(pairs),
        "hit_rate_excl_neutral": _hit_rate(pairs_excl),
        "exact_rate": _exact_rate(pairs),
        "n_excl_neutral": len(pairs_excl),
        "by_category": by_cat,
        "confusion_matrix": {"rows": CATS, "matrix": matrix},
        "by_confidence": by_conf,
        "by_week": by_week,
        "change_distribution": dist,
        "avg_change_by_prediction": {c: by_cat[c]["avg_change_pct"] for c in CATS},
        "baselines": baselines,
        "disclaimer": DISCLAIMER,
    }


def summary(results: list[dict]) -> dict:
    if not results:
        return {"period": None, "evaluated_sessions": 0, "insufficient_sessions": 0,
                "hit_rate": None, "hit_rate_excl_neutral_pred": None,
                "predictions": {c: 0 for c in CATS}, "correct": 0, "incorrect": 0,
                "data_completeness_pct": None, "last_processed_date": None, "daily": []}
    evaluated = [r for r in results if r["measurement"]["measurable"]]
    pairs = [(r["predicted"], r["measurement"]["actual"]) for r in evaluated
             if r["measurement"]["actual"]]
    pairs_excl = [(p, a) for p, a in pairs if p != "neutral"]
    correct = sum(1 for p, a in pairs if DIRECTION_OF[p] == DIRECTION_OF[a])
    return {
        "period": {"start": results[0]["date"], "end": results[-1]["date"],
                   "sessions": len(results)},
        "evaluated_sessions": len(pairs),
        "insufficient_sessions": sum(1 for r in results if r.get("insufficient")),
        "hit_rate": round(correct / len(pairs), 4) if pairs else None,
        "hit_rate_excl_neutral_pred": _hit_rate(pairs_excl),
        "exact_rate": _exact_rate(pairs),
        "predictions": {c: sum(1 for r in results if r["predicted"] == c) for c in CATS},
        "correct": correct,
        "incorrect": len(pairs) - correct,
        "data_completeness_pct": round(sum(r["data_quality"] for r in results)
                                       / len(results), 1),
        "last_processed_date": results[-1]["date"],
        "daily": [{"date": r["date"], "predicted": r["predicted"],
                   "actual": r["measurement"]["actual"],
                   "correct": r["measurement"]["correct"],
                   "exact": r["measurement"].get("exact"),
                   "score": r["score"], "confidence": r["confidence"],
                   "change_pct": r["measurement"]["change_pct"]} for r in results],
    }
