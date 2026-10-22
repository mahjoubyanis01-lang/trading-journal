"""Stockage local SQLite : résultats de séances, cache HTTP, erreurs de collecte.

Le cache HTTP conserve les réponses brutes des fournisseurs (URL + horodatage
de collecte) afin d'éviter les requêtes répétées et de rendre les résultats
reproductibles.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone

from .config import DB_PATH

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS http_cache (
    cache_key   TEXT PRIMARY KEY,
    url         TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    status      INTEGER NOT NULL,
    body        BLOB
);
CREATE TABLE IF NOT EXISTS session_results (
    session_date TEXT NOT NULL,
    params_hash  TEXT NOT NULL,
    computed_at  TEXT NOT NULL,
    payload      TEXT NOT NULL,
    PRIMARY KEY (session_date, params_hash)
);
CREATE TABLE IF NOT EXISTS collection_errors (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date TEXT,
    source       TEXT NOT NULL,
    message      TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    params      TEXT NOT NULL,
    status      TEXT NOT NULL,
    error       TEXT
);
"""


def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode=WAL")
        _local.conn = conn
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- cache HTTP ----------

def cache_get(cache_key: str, max_age_seconds: int | None = None) -> bytes | None:
    row = get_conn().execute(
        "SELECT fetched_at, status, body FROM http_cache WHERE cache_key=?", (cache_key,)
    ).fetchone()
    if row is None or row["status"] != 200:
        return None
    if max_age_seconds is not None:
        fetched = datetime.fromisoformat(row["fetched_at"])
        if (datetime.now(timezone.utc) - fetched).total_seconds() > max_age_seconds:
            return None
    return row["body"]


def cache_put(cache_key: str, url: str, status: int, body: bytes) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO http_cache (cache_key, url, fetched_at, status, body) VALUES (?,?,?,?,?)",
        (cache_key, url, now_iso(), status, body),
    )
    conn.commit()


# ---------- résultats de séances ----------

def save_session_result(session_date: str, params_hash: str, payload: dict) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO session_results (session_date, params_hash, computed_at, payload) VALUES (?,?,?,?)",
        (session_date, params_hash, now_iso(), json.dumps(payload)),
    )
    conn.commit()


def load_session_result(session_date: str, params_hash: str) -> dict | None:
    row = get_conn().execute(
        "SELECT payload FROM session_results WHERE session_date=? AND params_hash=?",
        (session_date, params_hash),
    ).fetchone()
    return json.loads(row["payload"]) if row else None


def load_all_results(params_hash: str) -> list[dict]:
    rows = get_conn().execute(
        "SELECT payload FROM session_results WHERE params_hash=? ORDER BY session_date",
        (params_hash,),
    ).fetchall()
    return [json.loads(r["payload"]) for r in rows]


def delete_results(params_hash: str, dates: list[str]) -> None:
    conn = get_conn()
    conn.executemany(
        "DELETE FROM session_results WHERE params_hash=? AND session_date=?",
        [(params_hash, d) for d in dates],
    )
    conn.commit()


# ---------- erreurs de collecte ----------

def log_error(session_date: str | None, source: str, message: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO collection_errors (session_date, source, message, created_at) VALUES (?,?,?,?)",
        (session_date, source, message[:2000], now_iso()),
    )
    conn.commit()


def list_errors(limit: int = 200) -> list[dict]:
    rows = get_conn().execute(
        "SELECT session_date, source, message, created_at FROM collection_errors ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        {"date": r["session_date"], "source": r["source"], "message": r["message"], "at": r["created_at"]}
        for r in rows
    ]


def clear_errors_for(session_date: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM collection_errors WHERE session_date=?", (session_date,))
    conn.commit()
