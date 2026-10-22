"""API FastAPI du S&P 500 Macro Bias Backtester (application locale)."""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

from . import db, export, stats
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


# ------------------------------------------------------------------ results

@app.get("/api/results/summary")
def results_summary():
    results, settings = _results()
    results = results[-settings["lookback_sessions"]:]
    return stats.summary(results)


@app.get("/api/results/sessions")
def results_sessions(predicted: str | None = None, actual: str | None = None,
                     correct: bool | None = None, min_confidence: int | None = None,
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
            "correct": m["correct"], "open_price": m["open_price"],
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
    return stats.compute_stats(results, settings["neutral_band_pct"])


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
