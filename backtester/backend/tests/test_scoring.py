"""Moteur de score : seuils, données insuffisantes, cohérence."""
from app.engine.factors import Factor, preopen_move_factor, vix_factor
from app.engine.scoring import aggregate


def mk(fid, weight, score, available=True) -> Factor:
    f = Factor(fid, fid, weight)
    f.score = score
    f.available = available
    return f


def test_biais_haussier_au_dessus_du_seuil():
    factors = [mk("a", 25, 20), mk("b", 10, 8), mk("c", 10, 7)]
    agg = aggregate(factors, 25, -25)
    assert agg["score"] >= 25
    assert agg["bias"] == "bullish"


def test_biais_baissier():
    factors = [mk("a", 25, -20), mk("b", 10, -8), mk("c", 10, -5)]
    agg = aggregate(factors, 25, -25)
    assert agg["bias"] == "bearish"


def test_biais_neutre_signaux_contradictoires():
    factors = [mk("a", 25, 20), mk("b", 25, -20), mk("c", 10, 1)]
    agg = aggregate(factors, 25, -25)
    assert agg["bias"] == "neutral"
    assert agg["agreement"] < 0.2


def test_donnees_insuffisantes_force_neutre():
    # Un seul facteur disponible, même très haussier -> neutre, insuffisant.
    factors = [mk("a", 25, 25), mk("b", 25, 0, available=False),
               mk("c", 25, 0, available=False), mk("d", 25, 0, available=False)]
    agg = aggregate(factors, 25, -25)
    assert agg["insufficient"] is True
    assert agg["bias"] == "neutral"
    assert agg["bias_reason"] == "données insuffisantes"


def test_score_borne_100():
    factors = [mk("a", 10, 10), mk("b", 10, 10), mk("c", 10, 10)]
    agg = aggregate(factors, 25, -25)
    assert agg["score"] == 100


def test_confiance_entre_0_et_100_et_sensible_a_la_completude():
    full = [mk(str(i), 10, 5) for i in range(8)]
    partial = full[:3] + [mk(str(i), 10, 0, available=False) for i in range(3, 8)]
    a_full = aggregate(full, 25, -25)
    a_partial = aggregate(partial, 25, -25)
    assert 0 <= a_partial["confidence"] <= a_full["confidence"] <= 100


def test_facteur_indisponible_score_nul():
    f = preopen_move_factor("es_preopen", "ES", None, 25, None)
    assert f.available is False and f.score == 0.0 and f.value == "n.d."


def test_facteur_preouverture_borne_par_poids():
    f = preopen_move_factor("es_preopen", "ES", 5.0, 25, None)  # +5 % énorme
    assert 0 < f.score <= 25


def test_vix_eleve_pese_negativement():
    f = vix_factor(32.0, 18.0, 10, None)
    assert f.score < -4
