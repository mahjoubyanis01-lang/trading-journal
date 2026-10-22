"""Mesure du mouvement réel du ES entre 9h30 New York et minuit Paris.

Conventions (documentées et testées) :
- Prix d'ouverture : OPEN de la bougie qui commence exactement à 09:30
  America/New_York. À défaut (donnée manquante), OPEN de la première bougie
  commençant dans les 30 minutes suivantes, signalé dans les limites.
- Prix à minuit Paris : si une bougie commence exactement à 00:00
  Europe/Paris (cas standard : réouverture CME à 18:00 ET quand le décalage
  vaut 6 h), son OPEN est le prix à minuit. Sinon, CLOSE de la dernière
  bougie entièrement terminée avant ou à minuit Paris (le CME est en pause
  de maintenance 17h-18h ET ; les semaines où le décalage Paris–NY vaut 5 h,
  minuit Paris tombe pendant la pause et le dernier prix traité est ~17:00 ET).
  L'horodatage réellement utilisé est toujours renvoyé.
- Variation points = prix final − prix initial ; variation % = variation
  relative au prix initial. Le seuil neutre (configurable, défaut ±0,10 %)
  sert uniquement à CLASSER la direction, jamais à modifier les prix mesurés.
- Le résultat mesure l'intervalle défini (9h30 NY → minuit Paris), pas la
  totalité de la séance américaine.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..providers.yahoo import Bar
from ..timeutil import PARIS, measure_end_paris, measure_start_ny


def classify_direction(change_pct: float | None, neutral_band_pct: float) -> str | None:
    if change_pct is None:
        return None
    if change_pct > neutral_band_pct:
        return "bullish"
    if change_pct < -neutral_band_pct:
        return "bearish"
    return "neutral"


def measure_session(bars: list[Bar], session_date: date, *,
                    measure_start_hhmm: str = "09:30",
                    neutral_band_pct: float = 0.10,
                    contract_note: str = "") -> dict:
    start_at = measure_start_ny(session_date, measure_start_hhmm)
    end_at = measure_end_paris(session_date)
    limitations: list[str] = []

    # --- prix d'ouverture ---
    open_price = open_ts = None
    exact = [b for b in bars if b.start == start_at]
    if exact:
        open_price, open_ts = exact[0].open, exact[0].start
    else:
        after = sorted((b for b in bars if start_at < b.start <= start_at + timedelta(minutes=30)),
                       key=lambda b: b.start)
        if after:
            open_price, open_ts = after[0].open, after[0].start
            limitations.append(
                f"Bougie de 09:30 NY absente : ouverture approximée par la bougie de "
                f"{after[0].start.astimezone(start_at.tzinfo).strftime('%H:%M')} NY.")

    # --- prix à minuit Paris ---
    close_price = close_ts = None
    at_midnight = [b for b in bars if b.start == end_at]
    if at_midnight:
        close_price, close_ts = at_midnight[0].open, at_midnight[0].start
    else:
        before = sorted((b for b in bars if b.end <= end_at), key=lambda b: b.end)
        if before:
            last = before[-1]
            close_price, close_ts = last.close, last.end
            gap_min = (end_at - last.end).total_seconds() / 60
            if gap_min > 90:
                limitations.append(
                    f"Dernier prix traité {gap_min:.0f} min avant minuit Paris "
                    f"({last.end.astimezone(PARIS).strftime('%H:%M')} Paris) — "
                    "pause de maintenance CME ou données manquantes.")

    if open_price is None or close_price is None:
        return {
            "open_price": open_price, "open_at": open_ts.isoformat() if open_ts else None,
            "close_price": close_price, "close_at": close_ts.isoformat() if close_ts else None,
            "change_points": None, "change_pct": None, "actual": None,
            "measurable": False, "contract_note": contract_note,
            "limitations": limitations + ["Prix d'ouverture ou de clôture introuvable : séance non mesurable."],
            "measure_start_at": start_at.isoformat(), "measure_end_at": end_at.isoformat(),
        }

    change_points = close_price - open_price
    change_pct = (close_price - open_price) / open_price * 100
    return {
        "open_price": round(open_price, 2), "open_at": open_ts.isoformat(),
        "close_price": round(close_price, 2), "close_at": close_ts.isoformat(),
        "change_points": round(change_points, 2), "change_pct": round(change_pct, 4),
        "actual": classify_direction(change_pct, neutral_band_pct),
        "measurable": True, "contract_note": contract_note,
        "limitations": limitations,
        "measure_start_at": start_at.isoformat(), "measure_end_at": end_at.isoformat(),
    }


def prediction_outcome(predicted: str, actual: str | None) -> bool | None:
    """Correct si biais prédit == direction observée (y compris neutre/neutre).
    None si la séance n'est pas mesurable."""
    if actual is None:
        return None
    return predicted == actual
