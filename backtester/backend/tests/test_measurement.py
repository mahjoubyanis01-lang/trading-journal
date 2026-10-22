"""Calcul de variation et classement directionnel."""
from datetime import date, datetime, timedelta

import pytest

from app.backtest.measurement import classify_direction, measure_session
from app.providers.yahoo import Bar
from app.timeutil import NEW_YORK, PARIS, measure_end_paris, measure_start_ny


def make_bars(session: date, prices: dict[str, float]) -> list[Bar]:
    """Construit des bougies 30 min : prices = {'HH:MM NY': open}."""
    bars = []
    for hhmm, px in prices.items():
        h, m = map(int, hhmm.split(":"))
        start = datetime(session.year, session.month, session.day, h, m, tzinfo=NEW_YORK)
        bars.append(Bar(start, start + timedelta(minutes=30), px, px + 1, px - 1, px + 0.5, 100))
    return bars


SESSION = date(2025, 7, 15)  # décalage 6 h : minuit Paris = 18:00 NY


def full_day_bars(open_930=6000.0, close_1630=6030.0):
    bars = make_bars(SESSION, {"09:00": 5995, "09:30": open_930, "10:00": 6005,
                               "16:00": 6020, "16:30": close_1630})
    return bars


def test_prix_ouverture_bougie_0930():
    m = measure_session(full_day_bars(), SESSION)
    assert m["open_price"] == 6000.0
    assert m["open_at"] == measure_start_ny(SESSION).isoformat()


def test_prix_minuit_bougie_exacte():
    # Une bougie commence exactement à minuit Paris (18:00 NY) : son OPEN est pris.
    bars = full_day_bars()
    midnight = measure_end_paris(SESSION)
    bars.append(Bar(midnight, midnight + timedelta(minutes=30), 6042.0, 6050, 6040, 6045, 100))
    m = measure_session(bars, SESSION)
    assert m["close_price"] == 6042.0
    assert m["close_at"] == midnight.isoformat()


def test_prix_minuit_repli_derniere_cloture():
    # Pas de bougie à minuit : close de la dernière bougie terminée avant minuit.
    m = measure_session(full_day_bars(close_1630=6030.0), SESSION)
    assert m["close_price"] == 6030.5  # close = open + 0.5 dans make_bars
    assert datetime.fromisoformat(m["close_at"]) <= measure_end_paris(SESSION)


def test_variation_points_et_pourcentage():
    bars = full_day_bars()
    midnight = measure_end_paris(SESSION)
    bars.append(Bar(midnight, midnight + timedelta(minutes=30), 6060.0, 6061, 6059, 6060, 1))
    m = measure_session(bars, SESSION)
    assert m["change_points"] == pytest.approx(60.0)
    assert m["change_pct"] == pytest.approx(1.0)
    assert m["actual"] == "bullish"


def test_seuil_neutre_ne_modifie_pas_les_prix():
    bars = full_day_bars()
    midnight = measure_end_paris(SESSION)
    bars.append(Bar(midnight, midnight + timedelta(minutes=30), 6003.0, 6004, 6002, 6003, 1))
    m = measure_session(bars, SESSION, neutral_band_pct=0.10)
    assert m["change_pct"] == pytest.approx(0.05)
    assert m["actual"] == "neutral"       # classé neutre…
    assert m["change_points"] == pytest.approx(3.0)  # …mais la variation reste affichée


def test_classification_directionnelle():
    assert classify_direction(0.25, 0.10) == "bullish"
    assert classify_direction(-0.25, 0.10) == "bearish"
    assert classify_direction(0.05, 0.10) == "neutral"
    assert classify_direction(-0.10, 0.10) == "neutral"  # borne incluse dans le neutre
    assert classify_direction(None, 0.10) is None


def test_seance_non_mesurable():
    m = measure_session([], SESSION)
    assert m["measurable"] is False
    assert m["change_pct"] is None and m["actual"] is None


def test_ouverture_manquante_approximee_et_signalee():
    bars = make_bars(SESSION, {"10:00": 6010, "16:30": 6030})
    m = measure_session(bars, SESSION)
    assert m["open_price"] == 6010
    assert any("approximée" in l for l in m["limitations"])
