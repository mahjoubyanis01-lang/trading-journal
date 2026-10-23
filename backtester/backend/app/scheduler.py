"""Planificateur de la notification quotidienne à l'heure limite.

Un thread discret attend 15h29 (heure de Paris, suit le réglage
``cutoff_paris``) chaque jour de semaine ; à l'heure dite il calcule le
verdict FIGÉ via le moteur complet puis notifie (toast Windows, Telegram si
configuré). Un garde-fou sur disque évite tout doublon, y compris après un
redémarrage de l'application.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta

from .config import DATA_DIR, load_settings
from .timeutil import PARIS, parse_hhmm

log = logging.getLogger("backtester.scheduler")

MARKER_PATH = DATA_DIR / "last_notification.txt"
FIRE_WINDOW_MINUTES = 15  # au-delà, on considère l'heure manquée pour ce jour


def next_trigger(now: datetime, cutoff_hhmm: str) -> datetime:
    """Prochain déclenchement : aujourd'hui à l'heure limite si elle n'est
    pas passée, sinon le prochain JOUR DE SEMAINE à l'heure limite."""
    target = datetime.combine(now.date(), parse_hhmm(cutoff_hhmm), tzinfo=PARIS)
    if now >= target:
        target += timedelta(days=1)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    return target


def already_sent(day_iso: str) -> bool:
    try:
        return MARKER_PATH.read_text().strip() == day_iso
    except OSError:
        return False


def mark_sent(day_iso: str) -> None:
    try:
        MARKER_PATH.write_text(day_iso)
    except OSError:
        log.warning("impossible d'écrire %s", MARKER_PATH)


def should_fire(now: datetime, cutoff_hhmm: str) -> bool:
    """Vrai dans la fenêtre [heure limite, +15 min[ d'un jour de semaine,
    si la notification du jour n'est pas déjà partie."""
    if now.weekday() >= 5:
        return False
    target = datetime.combine(now.date(), parse_hhmm(cutoff_hhmm), tzinfo=PARIS)
    if not (target <= now < target + timedelta(minutes=FIRE_WINDOW_MINUTES)):
        return False
    return not already_sent(now.date().isoformat())


def _fire() -> None:
    from .live import compute_live_verdict
    from .notify import notify_verdict

    day = datetime.now(PARIS).date().isoformat()
    mark_sent(day)  # marqué AVANT l'envoi : jamais de double notification
    verdict = compute_live_verdict(refresh=True)
    if not verdict.get("available"):
        log.info("notification %s non envoyée : %s", day, verdict.get("message"))
        return
    notify_verdict(verdict["session"])


def _loop() -> None:
    while True:
        try:
            settings = load_settings()
            enabled = settings.get("notifications", {}).get("enabled", False)
            now = datetime.now(PARIS)
            if enabled and should_fire(now, settings["cutoff_paris"]):
                _fire()
            # Sommeil court : les changements d'heure limite ou d'activation
            # sont pris en compte sans redémarrage.
            wait = (next_trigger(datetime.now(PARIS), settings["cutoff_paris"])
                    - datetime.now(PARIS)).total_seconds()
            time.sleep(max(5.0, min(30.0, wait)))
        except Exception:  # noqa: BLE001
            log.exception("erreur du planificateur de notification")
            time.sleep(60)


_started = False
_start_lock = threading.Lock()


def start() -> None:
    global _started
    with _start_lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, daemon=True, name="notify-scheduler").start()
    log.info("planificateur de notification démarré")
