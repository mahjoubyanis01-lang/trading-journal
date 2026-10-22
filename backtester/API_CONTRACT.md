# API Contract — S&P 500 Macro Bias Backtester

Backend: FastAPI sur `http://127.0.0.1:8000`. Toutes les routes sous `/api`.
Le frontend (Vite, port 5173) proxifie `/api` vers le backend.

Toutes les dates sont `YYYY-MM-DD` (date de séance, fuseau New York).
Tous les horodatages sont ISO-8601 avec offset (ex: `2026-10-21T15:29:00+02:00`).

## Verdict en 5 niveaux

Les biais prédits ET les directions réelles prennent leurs valeurs parmi :
`"strong_bullish" | "bullish" | "neutral" | "bearish" | "strong_bearish"`
(libellés français : Hausse affirmée, Hausse modérée, Neutre, Baisse modérée,
Baisse affirmée).

- Prédiction (score −100..+100) : `>= strong_bullish_threshold` (défaut +55) →
  strong_bullish ; `>= bullish_threshold` (+25) → bullish ;
  `<= strong_bearish_threshold` (−55) → strong_bearish ;
  `<= bearish_threshold` (−25) → bearish ; sinon neutral.
- Direction réelle (variation %) : `|chg| <= neutral_band_pct` (0,10) →
  neutral ; `> strong_band_pct` (0,50) → strong_bullish ; `> neutral_band` →
  bullish ; symétrique à la baisse.
- Deux notions de justesse : `correct` = même DIRECTION (hausse/baisse/neutre,
  intensité ignorée) ; `exact` = même classe parmi les 5. `null` = non évaluable.
- Les facteurs individuels (`factors[].direction`) restent sur 3 niveaux.

## GET /api/health
`{ "status": "ok", "version": "0.1.0" }`

## GET /api/config
```json
{
  "lookback_sessions": 30,              // 10|30|60|90|252
  "bullish_threshold": 25,              // score >= => hausse modérée
  "strong_bullish_threshold": 55,       // score >= => hausse affirmée
  "bearish_threshold": -25,             // score <= => baisse modérée
  "strong_bearish_threshold": -55,      // score <= => baisse affirmée
  "neutral_band_pct": 0.10,             // bande neutre direction réelle en %
  "strong_band_pct": 0.50,              // au-delà => direction affirmée
  "cutoff_paris": "15:29",              // heure limite info (Paris)
  "measure_start_ny": "09:30",          // début mesure (New York)
  "factor_weights": { "es_preopen": 25, "nq_preopen": 10, "europe": 10, "asia": 5,
                      "vix": 10, "yields": 10, "dxy": 5, "macro": 15,
                      "news": 15, "geopolitics": 15, "earnings": 10 },
  "es_provider": "yahoo"                // "yahoo" | "databento"
}
```

## PUT /api/config
Body: même forme (champs partiels acceptés). Retourne la config à jour.

## GET /api/providers/status
```json
{ "providers": [
  { "id": "yahoo",    "label": "Yahoo Finance (ES=F, indices, VIX…)", "requires_key": false,
    "configured": true, "key_masked": null, "categories": ["es_intraday","market_data"],
    "last_test": { "ok": true, "at": "…", "message": "…" } | null },
  { "id": "fred",     "label": "FRED / ALFRED (macro point-in-time)", "requires_key": true,
    "configured": false, "key_masked": "••••abcd" | null, "categories": ["macro"], "last_test": null },
  { "id": "gdelt",    "label": "GDELT (actualités)", "requires_key": false, ... },
  { "id": "finnhub",  "label": "Finnhub (résultats d'entreprises)", "requires_key": true, ... },
  { "id": "databento","label": "Databento (ES contrat par contrat)", "requires_key": true, ... }
] }
```

## POST /api/providers/{id}/key
Body `{ "key": "..." }` → `{ "ok": true, "key_masked": "••••abcd" }`. Jamais de clé complète en retour.
DELETE /api/providers/{id}/key → supprime la clé.

## POST /api/providers/{id}/test
→ `{ "ok": true|false, "message": "…", "at": "…" }`

## POST /api/backtest/run
Body `{ "sessions": 30, "force": false }` → `202 { "run_id": "…", "already_running": false }`
`force=true` recalcule les séances déjà en base.

## GET /api/backtest/status
```json
{ "running": true, "run_id": "…", "progress": { "done": 12, "total": 30, "current_date": "2026-10-07" },
  "started_at": "…", "finished_at": null, "error": null }
```

## GET /api/results/summary  (Page 1 — Tableau de bord)
```json
{
  "period": { "start": "2026-09-10", "end": "2026-10-21", "sessions": 30 },
  "evaluated_sessions": 27, "insufficient_sessions": 3,
  "hit_rate": 0.52,                      // sur séances évaluables
  "hit_rate_excl_neutral_pred": 0.55,
  "predictions": { "strong_bullish": 2, "bullish": 9, "neutral": 12, "bearish": 5, "strong_bearish": 2 },
  "correct": 14, "incorrect": 13,
  "data_completeness_pct": 78.5,
  "last_processed_date": "2026-10-21",
  "daily": [ { "date": "…", "predicted": "<5 niveaux>", "actual": "<5 niveaux>",
               "correct": true|false|null, "exact": true|false|null,
               "score": 31, "confidence": 62, "change_pct": 0.42 } ]
}
```
`null` partout si aucun backtest. `correct: null` = séance non évaluable.

## GET /api/results/sessions
Query params optionnels: `predicted`, `actual`, `correct` (`true|false`), `min_confidence`, `min_quality`, `date_from`, `date_to`.
```json
{ "sessions": [ {
  "date": "2026-10-21", "predicted": "bullish", "score": 31, "confidence": 62,
  "actual": "bearish", "change_points": -18.5, "change_pct": -0.27,
  "correct": false, "exact": false,
  "open_price": 6935.25, "close_price": 6916.75,
  "data_quality": 72, "insufficient": false,
  "bullish_summary": "…", "bearish_summary": "…"
} ] }
```

## GET /api/results/sessions/{date}  (Page 3 — détail)
```json
{
  "date": "2026-10-21",
  "cutoff_at": "2026-10-21T15:29:00+02:00",
  "measure_start_at": "2026-10-21T09:30:00-04:00",
  "measure_end_at": "2026-10-22T00:00:00+02:00",
  "predicted": "bullish", "score": 31, "confidence": 62,
  "reasoning": "texte synthétique…",
  "macro_summary": "texte…",
  "factors": [ { "id": "es_preopen", "label": "ES avant ouverture", "value": "+0.35% vs clôture RTH précédente",
                 "score": 9.2, "max_weight": 25, "direction": "bullish|bearish|neutral",
                 "rationale": "…", "available": true, "as_of": "…" } ],
  "bullish_factors": ["…"], "bearish_factors": ["…"], "contradictions": ["…"],
  "news": [ { "title": "…", "source": "reuters.com", "published_at": "…", "url": "…",
              "sentiment": "positive|negative|neutral", "relevance": "high|medium|low",
              "category": "macro|fed|geopolitics|earnings|markets" } ],
  "macro_releases": [ { "series": "CPI", "name": "Consumer Price Index", "period": "2026-09",
      "released_at": "…", "value": 3.1, "previous": 3.0, "consensus": null,
      "consensus_available": false, "surprise_vs_previous": 0.1, "interpretation": "…" } ],
  "preopen_market": { "es_move_pct": 0.35, "nq_move_pct": 0.5, "europe_pct": 0.2, "nikkei_pct": -0.3,
      "vix_prev_close": 17.2, "vix_20d_avg": 16.1, "us10y_prev": 4.12, "us10y_change_bp": 3.0,
      "us2y_prev": 3.61, "dxy_prev_change_pct": -0.2, "oil_pct": 1.1, "gold_pct": 0.3,
      "as_of": "…" },   // chaque champ peut être null
  "measurement": {
    "open_price": 6935.25, "open_at": "…", "close_price": 6916.75, "close_at": "…",
    "change_points": -18.5, "change_pct": -0.27, "actual": "bearish",
    "correct": false, "exact": false,
    "contract_note": "ES=F continu Yahoo (front month)…"
  },
  "intraday": [ { "t": "2026-10-21T09:30:00-04:00", "o": 6935.25, "h": …, "l": …, "c": … } ],
  "data_quality": 72, "insufficient": false,
  "limitations": ["Consensus historique indisponible…", "…"],
  "collection_errors": [ { "source": "fred", "message": "…" } ]
}
```
404 si la date n'existe pas.

## GET /api/results/stats  (Page 4)
```json
{
  "n_sessions": 30, "n_evaluated": 27, "n_insufficient": 3,
  "hit_rate": 0.52, "hit_rate_excl_neutral": 0.55, "exact_rate": 0.33,
  "by_category": { "strong_bullish": { "predicted": 2, "correct": 1, "exact": 1, "hit_rate": 0.5, "avg_change_pct": 0.6 },
                   "bullish": { … }, "neutral": { … }, "bearish": { … }, "strong_bearish": { … } },
  "confusion_matrix": { "rows": ["strong_bullish","bullish","neutral","bearish","strong_bearish"],
    "matrix": [[…5…],…5 lignes…] },          // lignes = prédit, colonnes = réel (5×5)
  "by_confidence": [ { "bucket": "0-33", "n": 5, "hit_rate": 0.4 }, { "bucket": "34-66", … }, { "bucket": "67-100", … } ],
  "by_week": [ { "week": "2026-W41", "n": 5, "correct": 3, "hit_rate": 0.6 } ],
  "change_distribution": [ { "bin": "-1.0% à -0.5%", "count": 4 } ],
  "avg_change_by_prediction": { "strong_bullish": 0.6, "bullish": 0.21, "neutral": 0.08, "bearish": -0.05, "strong_bearish": -0.4 },
  "baselines": [ { "id": "always_up", "label": "Toujours haussier", "hit_rate": 0.48, "n": 27 },
                 { "id": "always_down", … }, { "id": "follow_preopen", … }, { "id": "prior_day_momentum", … } ],
  "disclaimer": "Résultats exploratoires sur un petit échantillon…"
}
```

## GET /api/errors
`{ "errors": [ { "date": "…", "source": "fred", "message": "…", "at": "…" } ] }`

## GET /api/export/csv  → fichier CSV (une ligne/séance)
## GET /api/export/json → fichier JSON (analyses détaillées complètes)
