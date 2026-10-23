"""Planificateur de notification : prochain déclenchement, fenêtre, doublons."""
from datetime import datetime

from app import scheduler
from app.timeutil import PARIS


def dt(y, m, d, h, mi):
    return datetime(y, m, d, h, mi, tzinfo=PARIS)


def test_prochain_declenchement_aujourdhui_avant_heure():
    # Jeudi 10h -> aujourd'hui 15h29.
    t = scheduler.next_trigger(dt(2026, 10, 22, 10, 0), "15:29")
    assert t == dt(2026, 10, 22, 15, 29)


def test_prochain_declenchement_apres_heure_jour_suivant():
    # Jeudi 16h -> vendredi 15h29.
    t = scheduler.next_trigger(dt(2026, 10, 22, 16, 0), "15:29")
    assert t == dt(2026, 10, 23, 15, 29)


def test_week_end_saute():
    # Vendredi 16h -> lundi 15h29 (samedi et dimanche sautés).
    t = scheduler.next_trigger(dt(2026, 10, 23, 16, 0), "15:29")
    assert t == dt(2026, 10, 26, 15, 29)
    assert t.weekday() == 0


def test_fenetre_de_tir(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, "MARKER_PATH", tmp_path / "last.txt")
    # Dans la fenêtre [15:29, 15:44[ un jour de semaine.
    assert scheduler.should_fire(dt(2026, 10, 22, 15, 29), "15:29") is True
    assert scheduler.should_fire(dt(2026, 10, 22, 15, 43), "15:29") is True
    # Hors fenêtre : avant l'heure, trop tard, ou week-end.
    assert scheduler.should_fire(dt(2026, 10, 22, 15, 28), "15:29") is False
    assert scheduler.should_fire(dt(2026, 10, 22, 15, 45), "15:29") is False
    assert scheduler.should_fire(dt(2026, 10, 24, 15, 30), "15:29") is False  # samedi


def test_pas_de_doublon(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, "MARKER_PATH", tmp_path / "last.txt")
    now = dt(2026, 10, 22, 15, 30)
    assert scheduler.should_fire(now, "15:29") is True
    scheduler.mark_sent("2026-10-22")
    assert scheduler.should_fire(now, "15:29") is False
    # Le lendemain, la notification repart.
    assert scheduler.should_fire(dt(2026, 10, 23, 15, 30), "15:29") is True


def test_message_notification():
    from app.notify import build_verdict_message
    session = {"date": "2026-10-22", "predicted": "bearish", "score": -44.0,
               "confidence": 86, "provisional": False, "insufficient": False,
               "factors": [{"available": True}] * 8 + [{"available": False}] * 3,
               "news": [{}] * 60}
    title, body = build_verdict_message(session)
    assert "BAISSE MODÉRÉE" in title and "2026-10-22" in title
    assert "-44" in body and "86/100" in body and "figé" in body and "8/11" in body
