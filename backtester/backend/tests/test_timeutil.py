"""Le décalage Paris–New York n'est jamais supposé constant."""
from datetime import date, timedelta

from app.timeutil import cutoff_paris, measure_end_paris, measure_start_ny


def offset_hours(d: date) -> float:
    c = cutoff_paris(d)
    s = measure_start_ny(d)
    # Décalage réel Paris - New York ce jour-là (via les instants absolus).
    return (s.utcoffset() - c.utcoffset()).total_seconds() / -3600


def test_offset_usuel_6h():
    # Mi-juillet (CEST / EDT) et mi-janvier (CET / EST) : 6 h.
    assert offset_hours(date(2025, 7, 15)) == 6
    assert offset_hours(date(2025, 1, 15)) == 6


def test_offset_5h_entre_bascules_automne():
    # Entre la fin du DST européen (26 oct 2025) et américain (2 nov 2025) : 5 h.
    assert offset_hours(date(2025, 10, 28)) == 5


def test_offset_5h_entre_bascules_printemps():
    # Entre le passage US (9 mars 2025) et européen (30 mars 2025) : 5 h.
    assert offset_hours(date(2025, 3, 12)) == 5


def test_cutoff_avant_ouverture_quand_decalage_6h():
    d = date(2025, 7, 15)
    assert cutoff_paris(d) < measure_start_ny(d)


def test_cutoff_apres_935_ny_quand_decalage_5h():
    # Décalage 5 h : 15:29 Paris = 10:29 NY, APRÈS l'ouverture de 9h30.
    # Le code doit rester cohérent (les deux instants sont absolus).
    d = date(2025, 3, 12)
    assert cutoff_paris(d) > measure_start_ny(d)


def test_fin_mesure_minuit_paris_lendemain():
    d = date(2025, 7, 15)
    end = measure_end_paris(d)
    assert end.date() == d + timedelta(days=1)
    assert (end.hour, end.minute) == (0, 0)
    assert str(end.tzinfo) == "Europe/Paris"


def test_duree_fenetre_varie_avec_les_bascules():
    # 9h30 NY -> minuit Paris : 8h30 en régime 6 h ; en régime 5 h, minuit
    # Paris tombe à 19h00 NY et la fenêtre s'allonge à 9h30.
    d6, d5 = date(2025, 7, 15), date(2025, 3, 12)
    dur6 = measure_end_paris(d6) - measure_start_ny(d6)
    dur5 = measure_end_paris(d5) - measure_start_ny(d5)
    assert dur6 == timedelta(hours=8, minutes=30)
    assert dur5 == timedelta(hours=9, minutes=30)
