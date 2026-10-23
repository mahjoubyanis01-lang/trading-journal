"""API FastAPI du S&P 500 Macro Bias Backtester (application locale).

Sert aussi l'interface compilée (frontend/dist) : en double-cliquant sur le
lanceur Windows, un seul processus Python suffit (pas besoin de Node.js),
l'application s'ouvre sur http://127.0.0.1:8000.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel

from . import db, export, stats
from . import notify as notify_mod
from .backtest.runner import STATE, params_hash, start_backtest
from .config import (ALLOWED_LOOKBACKS, get_api_key, load_settings, mask_key,
                     save_settings, set_api_key)
from .providers import databento, finnhub, fred, gdelt, yahoo

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("backtester")

app = FastAPI(title="S&P 500 Macro Bias Backtester", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

PROVIDERS = {
    "yahoo": {"label": "Yahoo Finance (ES=F, indices, VIX…)", "requires_key": False,
              "categories": ["es_intraday", "market_data"], "test": yahoo.test_connection},
    "fred": {"label": "FRED / ALFRED (macro point-in-time)", "requires_key": True,
             "categories": ["macro", "rates"], "test": fred.test_connection},
    "gdelt": {"label": "GDELT (actualités horodatées)", "requires_key": False,
              "categories": ["news", "geopolitics"], "test": gdelt.test_connection},
    "finnhub": {"label": "Finnhub (résultats d'entreprises)", "requires_key": True,
                "categories": ["earnings"], "test": finnhub.test_connection},
    "databento": {"label": "Databento (ES contrat par contrat, payant)", "requires_key": True,
                  "categories": ["es_intraday"], "test": databento.test_connection},
    "telegram": {"label": "Telegram (notification du verdict)", "requires_key": True,
                 "categories": ["notifications"],
                 "test": lambda: notify_mod.send_telegram(
                     "S&P 500 Backtester : connexion Telegram OK.")},
}
_last_tests: dict[str, dict] = {}


def _results():
    settings = load_settings()
    return db.load_all_results(params_hash(settings)), settings


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


# ------------------------------------------------------------------ config

class ConfigUpdate(BaseModel):
    lookback_sessions: int | None = None
    bullish_threshold: float | None = None
    bearish_threshold: float | None = None
    neutral_band_pct: float | None = None
    cutoff_paris: str | None = None
    measure_start_ny: str | None = None
    factor_weights: dict[str, float] | None = None
    es_provider: str | None = None


@app.get("/api/config")
def get_config():
    return load_settings()


@app.put("/api/config")
def put_config(update: ConfigUpdate):
    try:
        return save_settings(update.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(400, str(e))


# ------------------------------------------------------------------ providers

@app.get("/api/providers/status")
def providers_status():
    out = []
    for pid, meta in PROVIDERS.items():
        key = get_api_key(pid) if meta["requires_key"] else None
        out.append({
            "id": pid, "label": meta["label"], "requires_key": meta["requires_key"],
            "configured": (bool(key) if meta["requires_key"] else True),
            "key_masked": mask_key(key),
            "categories": meta["categories"],
            "last_test": _last_tests.get(pid),
        })
    return {"providers": out}


class KeyBody(BaseModel):
    key: str


@app.post("/api/providers/{pid}/key")
def set_key(pid: str, body: KeyBody):
    if pid not in PROVIDERS or not PROVIDERS[pid]["requires_key"]:
        raise HTTPException(404, "fournisseur inconnu ou sans clé")
    set_api_key(pid, body.key)
    return {"ok": True, "key_masked": mask_key(body.key)}


@app.delete("/api/providers/{pid}/key")
def delete_key(pid: str):
    if pid not in PROVIDERS:
        raise HTTPException(404, "fournisseur inconnu")
    set_api_key(pid, None)
    return {"ok": True}


@app.post("/api/providers/{pid}/test")
def test_provider(pid: str):
    if pid not in PROVIDERS:
        raise HTTPException(404, "fournisseur inconnu")
    ok, message = PROVIDERS[pid]["test"]()
    result = {"ok": ok, "message": message, "at": db.now_iso()}
    _last_tests[pid] = result
    return result


# ------------------------------------------------------------------ backtest

class RunBody(BaseModel):
    sessions: int = 30
    force: bool = False


@app.post("/api/backtest/run", status_code=202)
def run_backtest(body: RunBody):
    if body.sessions not in ALLOWED_LOOKBACKS:
        raise HTTPException(400, f"sessions doit être parmi {sorted(ALLOWED_LOOKBACKS)}")
    save_settings({"lookback_sessions": body.sessions})
    run_id, already = start_backtest(body.sessions, body.force)
    return {"run_id": run_id, "already_running": already}


@app.get("/api/backtest/status")
def backtest_status():
    return STATE.snapshot()


# ------------------------------------------------------------------ live

@app.get("/api/live/verdict")
def live_verdict(refresh: bool = False):
    """Verdict du JOUR par le moteur complet (voir app.live) ; cache 120 s."""
    from .live import compute_live_verdict
    return compute_live_verdict(refresh)


# ------------------------------------------------------------- notifications

@app.get("/api/notify/status")
def notify_status():
    import platform as _platform
    from .scheduler import MARKER_PATH, next_trigger
    from .timeutil import PARIS
    from datetime import datetime as _dt
    settings = load_settings()
    notif = settings.get("notifications", {})
    last = None
    try:
        last = MARKER_PATH.read_text().strip() or None
    except OSError:
        pass
    return {
        "enabled": notif.get("enabled", False),
        "cutoff_paris": settings["cutoff_paris"],
        "next_trigger": next_trigger(_dt.now(PARIS), settings["cutoff_paris"]).isoformat(),
        "last_sent_date": last,
        "windows_toast_available": _platform.system() == "Windows",
        "telegram_configured": bool(get_api_key("telegram")
                                    and notif.get("telegram_chat_id")),
    }


@app.post("/api/notify/test")
def notify_test():
    """Envoie immédiatement une notification de test sur chaque canal."""
    from .notify import send_telegram, send_windows_toast
    title = "S&P 500 Backtester — test"
    body = "La notification quotidienne fonctionnera à l'heure limite (jours de semaine)."
    ok_t, msg_t = send_windows_toast(title, body)
    out = {"toast": {"ok": ok_t, "message": msg_t}, "telegram": None}
    ok_g, msg_g = send_telegram(f"{title}\n{body}")
    out["telegram"] = {"ok": ok_g, "message": msg_g}
    return out


@app.on_event("startup")
def _start_scheduler():
    from . import scheduler
    scheduler.start()


# ------------------------------------------------------------------ results

@app.get("/api/results/summary")
def results_summary():
    results, settings = _results()
    results = results[-settings["lookback_sessions"]:]
    return stats.summary(results)


@app.get("/api/results/sessions")
def results_sessions(predicted: str | None = None, actual: str | None = None,
                     correct: bool | None = None, exact: bool | None = None,
                     min_confidence: int | None = None,
                     min_quality: int | None = None, date_from: str | None = None,
                     date_to: str | None = None):
    results, settings = _results()
    results = results[-settings["lookback_sessions"]:]
    out = []
    for r in results:
        m = r["measurement"]
        if predicted and r["predicted"] != predicted:
            continue
        if actual and m["actual"] != actual:
            continue
        if correct is not None and m["correct"] != correct:
            continue
        if exact is not None and m.get("exact") != exact:
            continue
        if min_confidence is not None and r["confidence"] < min_confidence:
            continue
        if min_quality is not None and r["data_quality"] < min_quality:
            continue
        if date_from and r["date"] < date_from:
            continue
        if date_to and r["date"] > date_to:
            continue
        out.append({
            "date": r["date"], "predicted": r["predicted"], "score": r["score"],
            "confidence": r["confidence"], "actual": m["actual"],
            "change_points": m["change_points"], "change_pct": m["change_pct"],
            "correct": m["correct"], "exact": m.get("exact"),
            "open_price": m["open_price"],
            "close_price": m["close_price"], "data_quality": r["data_quality"],
            "insufficient": r["insufficient"],
            "bullish_summary": " · ".join(r["bullish_factors"][:2]) or "—",
            "bearish_summary": " · ".join(r["bearish_factors"][:2]) or "—",
        })
    return {"sessions": out}


@app.get("/api/results/sessions/{session_date}")
def result_detail(session_date: str):
    results, settings = _results()
    for r in results:
        if r["date"] == session_date:
            return r
    raise HTTPException(404, f"aucune analyse pour la séance {session_date}")


@app.get("/api/results/stats")
def results_stats():
    results, settings = _results()
    results = results[-settings["lookback_sessions"]:]
    return stats.compute_stats(results, settings["neutral_band_pct"],
                               settings["strong_band_pct"])


@app.get("/api/errors")
def errors():
    return {"errors": db.list_errors()}


# ------------------------------------------------------------------ export

@app.get("/api/export/csv")
def export_csv():
    results, settings = _results()
    results = results[-settings["lookback_sessions"]:]
    return PlainTextResponse(
        export.to_csv(results), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=backtest_results.csv"})


@app.get("/api/export/json")
def export_json():
    results, settings = _results()
    results = results[-settings["lookback_sessions"]:]
    return Response(
        export.to_json(results), media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=backtest_analyses.json"})


# --------------------------------------------------- frontend compilé (SPA)
# Déclaré en dernier : les routes /api ci-dessus restent prioritaires.

DIST_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if DIST_DIR.is_dir():
    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        candidate = (DIST_DIR / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(DIST_DIR):
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")
