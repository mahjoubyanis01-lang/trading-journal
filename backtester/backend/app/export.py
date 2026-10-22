"""Exports CSV (une ligne par séance) et JSON (analyses complètes)."""
from __future__ import annotations

import csv
import io
import json

CSV_COLUMNS = [
    "date", "predicted", "score", "confidence", "actual", "correct",
    "open_price", "open_at", "close_price", "close_at",
    "change_points", "change_pct", "data_quality", "insufficient",
    "cutoff_at", "coverage", "bias_reason",
]


def to_csv(results: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for r in results:
        m = r["measurement"]
        w.writerow([
            r["date"], r["predicted"], r["score"], r["confidence"],
            m["actual"], m["correct"],
            m["open_price"], m["open_at"], m["close_price"], m["close_at"],
            m["change_points"], m["change_pct"], r["data_quality"],
            r["insufficient"], r["cutoff_at"], r["coverage"], r["bias_reason"],
        ])
    return buf.getvalue()


def to_json(results: list[dict]) -> str:
    return json.dumps({"sessions": results}, ensure_ascii=False, indent=2)
