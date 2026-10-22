"""Statistiques : matrice de confusion 5×5, taux direction/exact, baselines."""
from app.backtest.measurement import prediction_outcome
from app.stats import compute_stats, summary


def session(d, predicted, actual, change_pct, confidence=50, insufficient=False,
            es_pre=None):
    correct, exact = prediction_outcome(predicted, actual)
    return {
        "date": d, "predicted": predicted, "score": 30 if "bullish" in predicted
        else -30 if "bearish" in predicted else 0,
        "confidence": confidence, "insufficient": insufficient,
        "data_quality": 80, "bias_reason": "", "coverage": 80, "cutoff_at": "",
        "bullish_factors": [], "bearish_factors": [],
        "preopen_market": {"es_move_pct": es_pre},
        "measurement": {"measurable": actual is not None, "actual": actual,
                        "change_pct": change_pct, "change_points": None,
                        "correct": correct, "exact": exact,
                        "open_price": None, "open_at": None,
                        "close_price": None, "close_at": None},
    }


RESULTS = [
    session("2025-07-01", "bullish", "strong_bullish", 0.8, 80, es_pre=0.4),
    session("2025-07-02", "bullish", "bearish", -0.4, 70, es_pre=0.2),
    session("2025-07-03", "strong_bearish", "bearish", -0.4, 60, es_pre=-0.5),
    session("2025-07-04", "neutral", "neutral", 0.02, 30, es_pre=0.01),
    session("2025-07-07", "neutral", "bullish", 0.3, 20, es_pre=0.3),
    session("2025-07-08", "bullish", None, None, 10, insufficient=True),
]


def test_matrice_de_confusion_5x5():
    s = compute_stats(RESULTS, 0.10)
    assert s["confusion_matrix"]["rows"] == [
        "strong_bullish", "bullish", "neutral", "bearish", "strong_bearish"]
    m = {r: dict(zip(s["confusion_matrix"]["rows"], row))
         for r, row in zip(s["confusion_matrix"]["rows"], s["confusion_matrix"]["matrix"])}
    assert m["bullish"]["strong_bullish"] == 1
    assert m["bullish"]["bearish"] == 1
    assert m["strong_bearish"]["bearish"] == 1
    assert m["neutral"]["neutral"] == 1
    assert m["neutral"]["bullish"] == 1
    assert sum(sum(row) for row in s["confusion_matrix"]["matrix"]) == 5  # non mesurable exclue


def test_taux_direction_et_exact():
    s = compute_stats(RESULTS, 0.10)
    assert s["n_evaluated"] == 5
    # Direction correcte : bullish/strong_bullish ✓, bullish/bearish ✗,
    # strong_bearish/bearish ✓, neutral/neutral ✓, neutral/bullish ✗ -> 3/5.
    assert s["hit_rate"] == 0.6
    # Classe exacte : seul neutral/neutral -> 1/5.
    assert s["exact_rate"] == 0.2
    assert s["hit_rate_excl_neutral"] == round(2 / 3, 4)
    assert s["n_excl_neutral"] == 3
    assert s["by_category"]["bullish"]["correct"] == 1
    assert s["by_category"]["bullish"]["exact"] == 0


def test_baseline_toujours_haussier():
    s = compute_stats(RESULTS, 0.10)
    always_up = next(b for b in s["baselines"] if b["id"] == "always_up")
    assert always_up["n"] == 5
    assert always_up["hit_rate"] == 0.4   # 2 séances réellement haussières / 5


def test_baseline_suivre_preouverture():
    s = compute_stats(RESULTS, 0.10)
    fp = next(b for b in s["baselines"] if b["id"] == "follow_preopen")
    # es_pre: +0.4->bullish(réel bullish ✓), +0.2->bullish(bearish ✗),
    # -0.5->bearish(bearish ✓), +0.01->neutral(neutral ✓), +0.3->bullish(bullish ✓)
    assert fp["n"] == 5 and fp["hit_rate"] == 0.8


def test_resume_tableau_de_bord():
    s = summary(RESULTS)
    assert s["period"]["sessions"] == 6
    assert s["evaluated_sessions"] == 5
    assert s["correct"] == 3 and s["incorrect"] == 2
    assert s["insufficient_sessions"] == 1
    assert len(s["daily"]) == 6


def test_resume_vide():
    s = summary([])
    assert s["hit_rate"] is None and s["daily"] == []


def test_disclaimer_present():
    s = compute_stats(RESULTS, 0.10)
    assert "exploratoires" in s["disclaimer"]
    assert "rentabilité" in s["disclaimer"]
