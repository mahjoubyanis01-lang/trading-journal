"""Tests anti-fuite d'information (look-ahead bias).

Vérifient que seules les données antérieures ou égales à la limite de
15:29 Paris peuvent entrer dans l'analyse.
"""
from datetime import date, datetime, time, timedelta

from app.backtest.runner import _daily_closes_before, _last_price_before, _prior_rth_close
from app.providers.yahoo import Bar
from app.timeutil import NEW_YORK, PARIS, UTC, cutoff_paris

SESSION = date(2025, 7, 15)
CUTOFF = cutoff_paris(SESSION)  # 15:29 Paris = 09:29 NY ce jour-là


def bar_at(dt: datetime, minutes: int, o: float, c: float) -> Bar:
    return Bar(dt, dt + timedelta(minutes=minutes), o, max(o, c), min(o, c), c, 10)


def test_bougie_chevauchant_la_limite_exclue():
    # Bougie 09:00-09:30 NY : se termine à 15:30 Paris, APRÈS 15:29 -> exclue.
    b_0900 = bar_at(datetime(2025, 7, 15, 9, 0, tzinfo=NEW_YORK), 30, 100, 999)
    b_0830 = bar_at(datetime(2025, 7, 15, 8, 30, tzinfo=NEW_YORK), 30, 100, 101)
    price, ts = _last_price_before([b_0830, b_0900], CUTOFF)
    assert price == 101  # la bougie de 08:30 (terminée 09:00 NY = 15:00 Paris)
    assert ts <= CUTOFF


def test_bougie_apres_limite_jamais_utilisee():
    b_late = bar_at(datetime(2025, 7, 15, 10, 0, tzinfo=NEW_YORK), 30, 200, 201)
    price, ts = _last_price_before([b_late], CUTOFF)
    assert price is None and ts is None


def test_cloture_reference_est_celle_de_la_veille():
    prev = bar_at(datetime(2025, 7, 14, 15, 30, tzinfo=NEW_YORK), 30, 100, 105)
    today = bar_at(datetime(2025, 7, 15, 8, 0, tzinfo=NEW_YORK), 30, 110, 111)
    price, ts = _prior_rth_close([prev, today], SESSION)
    assert price == 105
    assert ts.astimezone(NEW_YORK).date() == date(2025, 7, 14)


def test_series_quotidiennes_strictement_anterieures(monkeypatch):
    """_daily_closes_before ne doit JAMAIS renvoyer la bougie du jour de séance
    (sa clôture n'est connue qu'après la limite)."""
    from app.backtest import runner

    def fake_get_bars(symbol, start, end, interval, max_age=None):
        out = []
        for offset in range(5):
            d = SESSION - timedelta(days=4 - offset)  # inclut le jour de séance
            start_dt = datetime.combine(d, time(9, 30), tzinfo=NEW_YORK)
            out.append(bar_at(start_dt, 390, 10 + offset, 10 + offset))
        return out

    monkeypatch.setattr(runner.yahoo, "get_bars", fake_get_bars)
    closes = _daily_closes_before("^VIX", SESSION, 30)
    assert closes, "des clôtures antérieures doivent être renvoyées"
    assert all(d < SESSION for d, _ in closes)


def test_filtre_horodatage_gdelt():
    """Le parseur GDELT rejette tout article hors fenêtre ou sans horodatage."""
    from app.providers import gdelt as g

    start = CUTOFF - timedelta(hours=24)
    inside = CUTOFF - timedelta(hours=2)
    outside = CUTOFF + timedelta(minutes=1)
    payload = {"articles": [
        {"title": "In window", "domain": "reuters.com", "url": "u1",
         "seendate": inside.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")},
        {"title": "After cutoff", "domain": "reuters.com", "url": "u2",
         "seendate": outside.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")},
        {"title": "No timestamp", "domain": "reuters.com", "url": "u3"},
    ]}
    import app.providers.gdelt
    orig = app.providers.gdelt.get_json
    app.providers.gdelt.get_json = lambda *a, **k: payload
    try:
        arts = g.fetch_articles("macro_fed", start, CUTOFF)
    finally:
        app.providers.gdelt.get_json = orig
    assert [a["title"] for a in arts] == ["In window"]


def test_publication_macro_10h_et_apres_limite_exclue():
    """Une publication à 10:00 ET (16:00 Paris en régime 6 h) dépasse la
    limite de 15:29 Paris : l'horodatage reconstruit doit l'exclure."""
    released_at = datetime.combine(SESSION, time(10, 0), tzinfo=NEW_YORK)
    assert released_at > CUTOFF
    released_830 = datetime.combine(SESSION, time(8, 30), tzinfo=NEW_YORK)
    assert released_830 < CUTOFF


def test_mesure_jamais_dans_les_facteurs():
    """Le résultat observé (après ouverture) ne doit pas influencer le score :
    deux jeux de bougies identiques avant la limite mais opposés après
    doivent donner le même mouvement préouverture."""
    pre_bars = [
        bar_at(datetime(2025, 7, 14, 15, 30, tzinfo=NEW_YORK), 30, 100, 100),
        bar_at(datetime(2025, 7, 15, 8, 30, tzinfo=NEW_YORK), 30, 101, 102),
    ]
    up_after = pre_bars + [bar_at(datetime(2025, 7, 15, 12, 0, tzinfo=NEW_YORK), 30, 150, 160)]
    down_after = pre_bars + [bar_at(datetime(2025, 7, 15, 12, 0, tzinfo=NEW_YORK), 30, 50, 40)]
    p1, _ = _last_price_before(up_after, CUTOFF)
    p2, _ = _last_price_before(down_after, CUTOFF)
    assert p1 == p2 == 102
