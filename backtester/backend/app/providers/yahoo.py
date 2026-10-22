"""Yahoo Finance (API chart non officielle, sans clé).

Rôles :
- Prix intraday du contrat E-mini S&P 500 continu ``ES=F`` (front month CME).
- Données de marché complémentaires : NQ=F, indices européens/asiatiques,
  ^VIX, ^TNX, DX-Y.NYB, CL=F, GC=F.
- Calendrier des séances via les bougies quotidiennes du ^GSPC.

Continuité des échéances ES : Yahoo publie sous ``ES=F`` le contrat le plus
actif (front month) et bascule d'échéance au roll, SANS ajustement rétroactif
des prix. Comme toutes nos mesures (ouverture 9h30 NY → minuit Paris, et
mouvement préouverture du même jour) sont intra-journée, les deux bornes de
chaque mesure proviennent du même contrat ; aucun écart de roll n'entre dans
les variations calculées. Les prix de contrats différents ne sont jamais
mélangés au sein d'une même mesure. Limite documentée : autour des dates de
roll (mars/juin/sept/déc), la comparaison « clôture veille → préouverture »
peut chevaucher deux contrats ; le champ ``contract_note`` le signale.

Limites intraday Yahoo : interval=30m disponible ~60 jours en arrière,
interval=1h ~730 jours. Au-delà de 60 jours, la précision 9h30/minuit n'est
plus garantie par Yahoo : le fournisseur Databento (payant) doit être
configuré pour un historique plus profond en vraies données de contrat.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .base import ProviderError, get_json
from ..timeutil import NEW_YORK, UTC, from_unix

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# Profondeur maximale des intervalles intraday chez Yahoo (jours).
INTRADAY_LIMITS = {"30m": 59, "1h": 729}


class Bar:
    __slots__ = ("start", "end", "open", "high", "low", "close", "volume")

    def __init__(self, start: datetime, end: datetime, o, h, l, c, v):
        self.start, self.end = start, end
        self.open, self.high, self.low, self.close, self.volume = o, h, l, c, v

    def to_dict(self) -> dict:
        return {"t": self.start.isoformat(), "o": self.open, "h": self.high,
                "l": self.low, "c": self.close, "v": self.volume}


def _interval_minutes(interval: str) -> int:
    return {"30m": 30, "1h": 60, "1d": 24 * 60}[interval]


def fetch_chart(symbol: str, period1: int, period2: int, interval: str,
                *, max_age: int | None = None) -> dict:
    data = get_json(
        CHART_URL.format(symbol=symbol),
        {"period1": period1, "period2": period2, "interval": interval,
         "includePrePost": "true", "events": "div,splits"},
        cache_namespace=f"yahoo:{symbol}:{interval}",
        max_age_seconds=max_age,
        min_interval=1.5,
    )
    chart = data.get("chart", {})
    if chart.get("error"):
        raise ProviderError(f"Yahoo {symbol}: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise ProviderError(f"Yahoo {symbol}: réponse vide")
    return results[0]


def get_bars(symbol: str, start_utc: datetime, end_utc: datetime, interval: str,
             *, max_age: int | None = None) -> list[Bar]:
    """Bougies [start, end) en UTC. Horodatage Yahoo = DÉBUT de bougie."""
    res = fetch_chart(symbol, int(start_utc.timestamp()), int(end_utc.timestamp()),
                      interval, max_age=max_age)
    ts = res.get("timestamp") or []
    quote = (res.get("indicators", {}).get("quote") or [{}])[0]
    step = timedelta(minutes=_interval_minutes(interval))
    bars: list[Bar] = []
    for i, t in enumerate(ts):
        o = (quote.get("open") or [None] * len(ts))[i]
        c = (quote.get("close") or [None] * len(ts))[i]
        if o is None or c is None:
            continue
        start = from_unix(t, UTC)
        bars.append(Bar(
            start, start + step, o,
            (quote.get("high") or [None] * len(ts))[i],
            (quote.get("low") or [None] * len(ts))[i],
            c,
            (quote.get("volume") or [None] * len(ts))[i],
        ))
    return bars


def intraday_available(session_date: date, interval: str = "30m") -> bool:
    limit = INTRADAY_LIMITS.get(interval)
    if limit is None:
        return True
    return (date.today() - session_date).days <= limit


def get_trading_sessions(n: int, *, today: date | None = None) -> list[date]:
    """Les N dernières séances NYSE COMPLÈTES (week-ends et jours fériés exclus),
    déduites des bougies quotidiennes réelles du ^GSPC. Une séance n'est
    retenue que si sa fenêtre de mesure (jusqu'à minuit Paris le lendemain)
    est entièrement passée — on exclut donc toujours la séance en cours."""
    today = today or date.today()
    end = datetime.combine(today + timedelta(days=2), datetime.min.time(), tzinfo=UTC)
    start = end - timedelta(days=max(30, int(n * 2.2)))
    res = fetch_chart("^GSPC", int(start.timestamp()), int(end.timestamp()), "1d",
                      max_age=6 * 3600)
    ts = res.get("timestamp") or []
    closes = (res.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    days: list[date] = []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        d = from_unix(t, NEW_YORK).date()
        if d < today and d not in days:
            days.append(d)
    if len(days) < n:
        raise ProviderError(
            f"Seules {len(days)} séances trouvées via ^GSPC (demandé: {n}). "
            "Élargissez la fenêtre ou vérifiez la connexion Yahoo.")
    return days[-n:]


def test_connection() -> tuple[bool, str]:
    try:
        res = fetch_chart("ES=F", int((datetime.now(UTC) - timedelta(days=3)).timestamp()),
                          int(datetime.now(UTC).timestamp()), "1d", max_age=60)
        sym = res.get("meta", {}).get("symbol")
        px = res.get("meta", {}).get("regularMarketPrice")
        return True, f"OK — {sym}, dernier prix {px}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)
