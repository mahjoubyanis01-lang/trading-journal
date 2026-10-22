"""Orchestrateur du backtest : collecte → facteurs → score → mesure → stockage.

Reprise sur interruption : chaque séance est stockée sous une clé
(date, hash des paramètres). Un nouveau lancement recharge les séances déjà
calculées avec les mêmes paramètres et ne recalcule que les manquantes
(sauf force=True).

Anti-fuite d'information (look-ahead) :
- Toute donnée de marché préouverture provient de bougies dont la FIN est
  antérieure ou égale à la limite de 15:29 Paris.
- Les séries quotidiennes (VIX, taux, dollar) n'utilisent que des bougies de
  jours STRICTEMENT antérieurs à la séance (leur clôture du jour n'est connue
  qu'après la limite). Exception documentée : les clôtures d'Asie (Nikkei),
  intervenues avant 9h heure de Paris, donc connues avant la limite.
- Les actualités sont filtrées sur leur horodatage GDELT <= limite.
- Les publications macro sont filtrées sur (date de vintage ALFRED + heure
  officielle de publication) <= limite — jamais sur la seule date.
- La mesure (9h30 NY → minuit Paris) est calculée APRÈS la prévision et
  n'entre dans aucun facteur.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import uuid
from datetime import date, datetime, time, timedelta

from .. import db
from ..config import get_api_key, load_settings
from ..engine import factors as F
from ..engine.scoring import aggregate, build_reasoning
from ..engine.sentiment import classify_title
from ..providers import databento, finnhub, fred, gdelt, yahoo
from ..providers.base import ProviderError
from ..timeutil import NEW_YORK, PARIS, UTC, cutoff_paris, measure_end_paris
from .measurement import measure_session, prediction_outcome

log = logging.getLogger("backtester.runner")

CONTRACT_NOTE_YAHOO = (
    "ES=F (Yahoo) : contrat E-mini S&P 500 continu front month CME, bascule "
    "d'échéance au roll sans ajustement rétroactif. Les deux bornes de chaque "
    "mesure intra-journée proviennent du même contrat ; autour des dates de "
    "roll trimestrielles, la comparaison avec la clôture de la veille peut "
    "chevaucher deux contrats.")
CONTRACT_NOTE_DATABENTO = (
    "Databento GLBX.MDP3, symbole continu ES.c.0 (front month par volume, "
    "sans ajustement de prix) : le contrat réel de chaque bougie est tracé.")


def params_hash(settings: dict) -> str:
    relevant = {k: settings[k] for k in
                ("bullish_threshold", "bearish_threshold", "neutral_band_pct",
                 "cutoff_paris", "measure_start_ny", "factor_weights", "es_provider")}
    return hashlib.sha256(json.dumps(relevant, sort_keys=True).encode()).hexdigest()[:16]


class RunState:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.run_id: str | None = None
        self.done = 0
        self.total = 0
        self.current_date: str | None = None
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.error: str | None = None

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "running": self.running, "run_id": self.run_id,
                "progress": {"done": self.done, "total": self.total,
                             "current_date": self.current_date},
                "started_at": self.started_at, "finished_at": self.finished_at,
                "error": self.error,
            }


STATE = RunState()


# ------------------------------------------------------------------ helpers

def _last_price_before(bars, cutoff_dt):
    """Close de la dernière bougie ENTIÈREMENT terminée avant la limite."""
    before = [b for b in bars if b.end <= cutoff_dt]
    if not before:
        return None, None
    last = max(before, key=lambda b: b.end)
    return last.close, last.end


def _prior_rth_close(bars, session_date: date):
    """Clôture de référence de la veille : dernier prix traité avant 16:00 NY
    du jour calendaire précédent la séance (clôture de la séance cash)."""
    ref = datetime.combine(session_date - timedelta(days=1), time(16, 0), tzinfo=NEW_YORK)
    # si la veille est un dimanche/jour férié, remonter jusqu'à 4 jours
    for back in range(0, 4):
        ref_try = ref - timedelta(days=back)
        price, ts = _last_price_before(bars, ref_try)
        if price is not None and (ref_try - ts) <= timedelta(hours=18):
            return price, ts
    return None, None


def _pct(a: float | None, b: float | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return round((a - b) / b * 100, 4)


def _daily_closes_before(symbol: str, session_date: date, n: int = 30):
    """Clôtures quotidiennes de jours STRICTEMENT antérieurs à la séance."""
    end = datetime.combine(session_date, time(0, 0), tzinfo=NEW_YORK)
    start = end - timedelta(days=n * 2 + 20)
    bars = yahoo.get_bars(symbol, start.astimezone(UTC), end.astimezone(UTC), "1d",
                          max_age=12 * 3600)
    out = []
    for b in bars:
        d = b.start.astimezone(NEW_YORK).date()
        if d < session_date and b.close is not None:
            out.append((d, b.close))
    return out[-n:]


def _normalize_yield(v: float | None) -> float | None:
    # ^TNX cote historiquement le rendement x10 (ex: 42.5 = 4.25 %).
    if v is None:
        return None
    return v / 10 if v > 20 else v


# ------------------------------------------------------------------ collecte

def collect_preopen_market(session_date: date, cutoff: datetime, es_bars, errors: list):
    pre: dict = {"as_of": None}

    es_pre, es_pre_ts = _last_price_before(es_bars, cutoff)
    es_ref, _ = _prior_rth_close(es_bars, session_date)
    pre["es_move_pct"] = _pct(es_pre, es_ref)
    pre["as_of"] = es_pre_ts.isoformat() if es_pre_ts else None

    win_start = datetime.combine(session_date - timedelta(days=4), time(0, 0), tzinfo=UTC)
    for key, symbol in (("nq_move_pct", "NQ=F"),):
        try:
            if yahoo.intraday_available(session_date):
                bars = yahoo.get_bars(symbol, win_start, cutoff.astimezone(UTC), "30m")
                price, _ = _last_price_before(bars, cutoff)
                ref, _ = _prior_rth_close(bars, session_date)
                pre[key] = _pct(price, ref)
            else:
                pre[key] = None
        except ProviderError as e:
            pre[key] = None
            errors.append(("yahoo", f"{symbol}: {e}"))

    # Europe : mouvement du jour (ouverture Europe -> limite), bougies 30 min.
    pre["europe_pct"] = None
    for symbol in ("^STOXX50E", "^GDAXI"):
        try:
            if not yahoo.intraday_available(session_date):
                break
            day_start = datetime.combine(session_date, time(8, 0), tzinfo=PARIS)
            bars = yahoo.get_bars(symbol, day_start.astimezone(UTC), cutoff.astimezone(UTC), "30m")
            usable = [b for b in bars if b.end <= cutoff]
            if len(usable) >= 2:
                pre["europe_pct"] = _pct(usable[-1].close, usable[0].open)
                pre["europe_symbol"] = symbol
                break
        except ProviderError as e:
            errors.append(("yahoo", f"{symbol}: {e}"))

    # Asie : clôture Nikkei du jour (intervenue ~08h Paris, avant la limite).
    pre["nikkei_pct"] = None
    try:
        end = datetime.combine(session_date + timedelta(days=1), time(0, 0), tzinfo=UTC)
        bars = yahoo.get_bars("^N225", end - timedelta(days=12), end, "1d", max_age=12 * 3600)
        closes = [(b.start.astimezone(UTC).date(), b.close) for b in bars if b.close]
        todays = [c for d, c in closes if d == session_date]
        prevs = [c for d, c in closes if d < session_date]
        if todays and prevs:
            pre["nikkei_pct"] = _pct(todays[-1], prevs[-1])
    except ProviderError as e:
        errors.append(("yahoo", f"^N225: {e}"))

    # VIX : clôture de la VEILLE uniquement (+ moyenne 20 séances antérieures).
    pre["vix_prev_close"] = pre["vix_20d_avg"] = None
    try:
        closes = _daily_closes_before("^VIX", session_date, 21)
        if closes:
            pre["vix_prev_close"] = round(closes[-1][1], 2)
            if len(closes) >= 10:
                pre["vix_20d_avg"] = round(sum(c for _, c in closes[-20:]) / len(closes[-20:]), 2)
    except ProviderError as e:
        errors.append(("yahoo", f"^VIX: {e}"))

    # Taux et dollar : veille uniquement. FRED (point-in-time) prioritaire.
    pre["us10y_prev"] = pre["us10y_change_bp"] = pre["us2y_prev"] = pre["dxy_prev_change_pct"] = None
    used_fred = False
    if get_api_key("fred"):
        try:
            s10 = fred.daily_series_asof("DGS10", session_date)
            s2 = fred.daily_series_asof("DGS2", session_date)
            if len(s10) >= 2:
                pre["us10y_prev"] = s10[-1][1]
                pre["us10y_change_bp"] = round((s10[-1][1] - s10[-2][1]) * 100, 1)
            if s2:
                pre["us2y_prev"] = s2[-1][1]
            used_fred = True
        except ProviderError as e:
            errors.append(("fred", f"taux: {e}"))
    if not used_fred:
        try:
            closes = _daily_closes_before("^TNX", session_date, 5)
            if len(closes) >= 2:
                y_now = _normalize_yield(closes[-1][1])
                y_prev = _normalize_yield(closes[-2][1])
                pre["us10y_prev"] = round(y_now, 3)
                pre["us10y_change_bp"] = round((y_now - y_prev) * 100, 1)
        except ProviderError as e:
            errors.append(("yahoo", f"^TNX: {e}"))
    try:
        closes = _daily_closes_before("DX-Y.NYB", session_date, 5)
        if len(closes) >= 2:
            pre["dxy_prev_change_pct"] = _pct(closes[-1][1], closes[-2][1])
    except ProviderError as e:
        errors.append(("yahoo", f"DXY: {e}"))

    # Pétrole / or : mouvement préouverture (30 min) si disponible.
    for key, symbol in (("oil_pct", "CL=F"), ("gold_pct", "GC=F")):
        pre[key] = None
        try:
            if yahoo.intraday_available(session_date):
                bars = yahoo.get_bars(symbol, win_start, cutoff.astimezone(UTC), "30m")
                price, _ = _last_price_before(bars, cutoff)
                ref, _ = _prior_rth_close(bars, session_date)
                pre[key] = _pct(price, ref)
        except ProviderError as e:
            errors.append(("yahoo", f"{symbol}: {e}"))

    return pre


def collect_news(session_date: date, cutoff: datetime, errors: list,
                 prev_session_date: date | None = None) -> list[dict]:
    """Fenêtre d'actualités : depuis la limite de la séance précédente (pour
    couvrir week-ends et jours fériés sans chevaucher deux analyses), bornée
    à 4 jours ; à défaut, 24 h (72 h le lundi)."""
    if prev_session_date is not None:
        start = cutoff_paris(prev_session_date, f"{cutoff.hour:02d}:{cutoff.minute:02d}")
        start = max(start, cutoff - timedelta(days=4))
    else:
        hours = 72 if session_date.weekday() == 0 else 24
        start = cutoff - timedelta(hours=hours)
    try:
        window = gdelt.fetch_window(start, cutoff)
    except ProviderError as e:
        errors.append(("gdelt", str(e)))
        return []
    articles: list[dict] = []
    for cat, arts in window.items():
        for a in arts:
            a["_sent"] = classify_title(a["title"])
            a["sentiment"] = a["_sent"]["sentiment"]
            a["relevance"] = "high" if a["trusted"] else "medium"
            articles.append(a)
    articles.sort(key=lambda a: a["published_at"], reverse=True)
    return articles


def get_es_bars(session_date: date, settings: dict, errors: list):
    """Bougies ES couvrant [veille 00:00 NY → lendemain 01:00 Paris]."""
    start = datetime.combine(session_date - timedelta(days=4), time(0, 0), tzinfo=NEW_YORK)
    end = measure_end_paris(session_date) + timedelta(hours=1)
    provider = settings.get("es_provider", "yahoo")
    if provider == "databento" and get_api_key("databento"):
        try:
            return databento.get_bars(start.astimezone(UTC), end.astimezone(UTC)), CONTRACT_NOTE_DATABENTO
        except ProviderError as e:
            errors.append(("databento", str(e) + " — repli sur Yahoo"))
    if not yahoo.intraday_available(session_date, "30m"):
        errors.append(("yahoo", "ES=F : intraday 30 min indisponible au-delà de ~60 jours ; "
                                "configurez Databento pour un historique plus profond"))
        return [], CONTRACT_NOTE_YAHOO
    bars = yahoo.get_bars("ES=F", start.astimezone(UTC), end.astimezone(UTC), "30m")
    return bars, CONTRACT_NOTE_YAHOO


# ------------------------------------------------------------------ séance

def analyze_session(session_date: date, settings: dict,
                    prev_session_date: date | None = None) -> dict:
    errors: list[tuple[str, str]] = []
    cutoff = cutoff_paris(session_date, settings["cutoff_paris"])
    weights = settings["factor_weights"]

    es_bars, contract_note = get_es_bars(session_date, settings, errors)
    pre = collect_preopen_market(session_date, cutoff, es_bars, errors)
    news = collect_news(session_date, cutoff, errors, prev_session_date)

    macro_releases: list[dict] = []
    if get_api_key("fred"):
        try:
            macro_releases = fred.releases_before_cutoff(session_date, cutoff)
        except ProviderError as e:
            errors.append(("fred", str(e)))
    else:
        errors.append(("fred", "non configuré : publications macro ignorées"))

    earnings: list[dict] = []
    finnhub_ok = bool(get_api_key("finnhub"))
    if finnhub_ok:
        try:
            earnings = finnhub.earnings_before_cutoff(session_date, cutoff)
        except ProviderError as e:
            errors.append(("finnhub", str(e)))
            finnhub_ok = False

    flist = [
        F.preopen_move_factor("es_preopen", "ES avant ouverture", pre.get("es_move_pct"),
                              weights["es_preopen"], pre.get("as_of")),
        F.preopen_move_factor("nq_preopen", "Nasdaq-100 (NQ) avant ouverture",
                              pre.get("nq_move_pct"), weights["nq_preopen"], pre.get("as_of"),
                              scale=0.8),
        F.preopen_move_factor("europe", "Marchés européens (séance en cours)",
                              pre.get("europe_pct"), weights["europe"], None, scale=0.9),
        F.preopen_move_factor("asia", "Asie (clôture Nikkei)", pre.get("nikkei_pct"),
                              weights["asia"], None, scale=1.2),
        F.vix_factor(pre.get("vix_prev_close"), pre.get("vix_20d_avg"), weights["vix"], None),
        F.yields_factor(pre.get("us10y_prev"), pre.get("us10y_change_bp"),
                        pre.get("us2y_prev"), weights["yields"], None),
        F.dxy_factor(pre.get("dxy_prev_change_pct"), weights["dxy"], None),
        F.macro_factor(macro_releases, weights["macro"]),
        F.news_factor(news, weights["news"]),
        F.geopolitics_factor(news, weights["geopolitics"]),
        F.earnings_factor(earnings, weights["earnings"], finnhub_ok),
    ]

    agg = aggregate(flist, settings["bullish_threshold"], settings["bearish_threshold"])
    reasoning = build_reasoning(flist, agg, settings["bullish_threshold"],
                                settings["bearish_threshold"])

    meas = measure_session(es_bars, session_date,
                           measure_start_hhmm=settings["measure_start_ny"],
                           neutral_band_pct=settings["neutral_band_pct"],
                           contract_note=contract_note)
    correct = prediction_outcome(agg["bias"], meas["actual"])

    limitations = list(meas["limitations"])
    limitations.append("Consensus des économistes historiquement indisponible sur les "
                       "sources gratuites : surprises mesurées vs valeur précédente.")
    limitations.append("Sentiment des actualités estimé par lexique heuristique sur les "
                       "titres (GDELT), horodatage = découverte GDELT (±15 min).")
    if not get_api_key("fred"):
        limitations.append("FRED non configuré : aucune publication macro point-in-time utilisée.")
    if not finnhub_ok:
        limitations.append("Finnhub non configuré : résultats d'entreprises non pris en compte.")
    if not news:
        limitations.append("Aucune actualité récupérée pour cette séance.")
    if agg["insufficient"]:
        limitations.append("Couverture de données insuffisante : séance classée "
                           "« NEUTRE — données insuffisantes ».")

    # Qualité des données : couverture des facteurs + mesurabilité.
    quality = round(0.7 * agg["coverage"] + 30 * (1 if meas["measurable"] else 0))

    macro_summary = _macro_summary(pre, macro_releases, news)

    intraday = [b.to_dict() for b in es_bars
                if meas["measurable"]
                and b.start >= datetime.fromisoformat(meas["measure_start_at"])
                and b.end <= datetime.fromisoformat(meas["measure_end_at"]) + timedelta(minutes=30)]

    for a in news:
        a.pop("_sent", None)

    return {
        "date": session_date.isoformat(),
        "cutoff_at": cutoff.isoformat(),
        "measure_start_at": meas["measure_start_at"],
        "measure_end_at": meas["measure_end_at"],
        "predicted": agg["bias"],
        "bias_reason": agg["bias_reason"],
        "score": agg["score"],
        "confidence": agg["confidence"],
        "coverage": agg["coverage"],
        "insufficient": agg["insufficient"],
        "reasoning": reasoning["reasoning"],
        "macro_summary": macro_summary,
        "factors": [f.to_dict() for f in flist],
        "bullish_factors": reasoning["bullish_factors"],
        "bearish_factors": reasoning["bearish_factors"],
        "contradictions": reasoning["contradictions"],
        "news": news[:60],
        "macro_releases": macro_releases,
        "earnings": earnings,
        "preopen_market": pre,
        "measurement": {k: meas[k] for k in
                        ("open_price", "open_at", "close_price", "close_at",
                         "change_points", "change_pct", "actual", "measurable",
                         "contract_note")} | {"correct": correct},
        "intraday": intraday,
        "data_quality": quality,
        "limitations": limitations,
        "collection_errors": [{"source": s, "message": m} for s, m in errors],
    }


def _macro_summary(pre: dict, releases: list[dict], news: list[dict]) -> str:
    parts = []
    if pre.get("us10y_prev") is not None:
        chg = pre.get("us10y_change_bp")
        parts.append(f"US 10 ans {pre['us10y_prev']:.2f} %"
                     + (f" ({chg:+.0f} pb la veille)" if chg is not None else ""))
    if pre.get("vix_prev_close") is not None:
        parts.append(f"VIX {pre['vix_prev_close']:.1f}")
    if pre.get("dxy_prev_change_pct") is not None:
        parts.append(f"dollar {pre['dxy_prev_change_pct']:+.2f} % la veille")
    if releases:
        parts.append(f"{len(releases)} publication(s) macro dans la fenêtre : "
                     + ", ".join(r["name"] for r in releases[:4]))
    else:
        parts.append("aucune publication macro recensée dans la fenêtre")
    n_geo = sum(1 for a in news if a.get("category") == "geopolitics")
    if n_geo:
        parts.append(f"{n_geo} titres géopolitiques suivis")
    return "Contexte au moment de la limite : " + " ; ".join(parts) + "."


# ------------------------------------------------------------------ run

def run_backtest(n_sessions: int, force: bool = False) -> None:
    settings = load_settings()
    ph = params_hash(settings)
    run_id = STATE.run_id or str(uuid.uuid4())[:8]
    conn_params = json.dumps({"sessions": n_sessions, "force": force, "params_hash": ph})
    db.get_conn().execute(
        "INSERT OR REPLACE INTO runs (run_id, started_at, params, status) VALUES (?,?,?,?)",
        (run_id, db.now_iso(), conn_params, "running"))
    db.get_conn().commit()
    try:
        dates = yahoo.get_trading_sessions(n_sessions)
        with STATE.lock:
            STATE.total = len(dates)
        for i, d in enumerate(dates):
            with STATE.lock:
                STATE.current_date = d.isoformat()
                STATE.done = i
            existing = None if force else db.load_session_result(d.isoformat(), ph)
            if existing is not None:
                continue
            db.clear_errors_for(d.isoformat())
            try:
                result = analyze_session(d, settings, dates[i - 1] if i > 0 else None)
            except Exception as e:  # noqa: BLE001
                log.exception("échec séance %s", d)
                db.log_error(d.isoformat(), "runner", f"échec de l'analyse: {e}")
                continue
            for err in result["collection_errors"]:
                db.log_error(d.isoformat(), err["source"], err["message"])
            db.save_session_result(d.isoformat(), ph, result)
        with STATE.lock:
            STATE.done = len(dates)
        db.get_conn().execute("UPDATE runs SET finished_at=?, status=? WHERE run_id=?",
                              (db.now_iso(), "done", run_id))
        db.get_conn().commit()
    except Exception as e:  # noqa: BLE001
        log.exception("échec du backtest")
        with STATE.lock:
            STATE.error = str(e)
        db.get_conn().execute("UPDATE runs SET finished_at=?, status=?, error=? WHERE run_id=?",
                              (db.now_iso(), "failed", run_id, str(e)))
        db.get_conn().commit()
    finally:
        with STATE.lock:
            STATE.running = False
            STATE.finished_at = db.now_iso()


def start_backtest(n_sessions: int, force: bool = False) -> tuple[str, bool]:
    with STATE.lock:
        if STATE.running:
            return STATE.run_id or "", True
        STATE.running = True
        STATE.run_id = str(uuid.uuid4())[:8]
        STATE.done = 0
        STATE.total = n_sessions
        STATE.current_date = None
        STATE.started_at = db.now_iso()
        STATE.finished_at = None
        STATE.error = None
        run_id = STATE.run_id
    t = threading.Thread(target=run_backtest, args=(n_sessions, force), daemon=True)
    t.start()
    return run_id, False
