"""Paramètres de l'application.

- Les réglages modifiables (seuils, poids, période…) vivent dans
  ``data/settings.json`` et sont édités via l'API (PUT /api/config).
- Les clés API vivent dans ``data/.keys.env`` (jamais commité, jamais renvoyé
  en clair par l'API) ; ``.env`` à la racine du backend est aussi lu au
  démarrage pour amorcer les clés (FRED_API_KEY, FINNHUB_API_KEY,
  DATABENTO_API_KEY, NEWSAPI_API_KEY).
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from dotenv import dotenv_values

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("BACKTESTER_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS_PATH = DATA_DIR / "settings.json"
KEYS_PATH = DATA_DIR / ".keys.env"
DB_PATH = DATA_DIR / "backtest.db"

DEFAULT_SETTINGS: dict = {
    "lookback_sessions": 30,
    "bullish_threshold": 25,
    "strong_bullish_threshold": 55,
    "bearish_threshold": -25,
    "strong_bearish_threshold": -55,
    "neutral_band_pct": 0.10,
    "strong_band_pct": 0.50,
    "cutoff_paris": "15:29",
    "measure_start_ny": "09:30",
    "factor_weights": {
        "es_preopen": 25,
        "nq_preopen": 10,
        "europe": 10,
        "asia": 5,
        "vix": 10,
        "yields": 10,
        "dxy": 5,
        "macro": 15,
        "news": 15,
        "geopolitics": 15,
        "earnings": 10,
    },
    "es_provider": "yahoo",
}

ALLOWED_LOOKBACKS = {10, 30, 60, 90, 252}
KEY_PROVIDERS = {"fred": "FRED_API_KEY", "finnhub": "FINNHUB_API_KEY",
                 "databento": "DATABENTO_API_KEY", "newsapi": "NEWSAPI_API_KEY"}

_lock = threading.Lock()


def load_settings() -> dict:
    s = dict(DEFAULT_SETTINGS)
    if SETTINGS_PATH.exists():
        try:
            stored = json.loads(SETTINGS_PATH.read_text())
            for k, v in stored.items():
                if k == "factor_weights" and isinstance(v, dict):
                    fw = dict(DEFAULT_SETTINGS["factor_weights"])
                    fw.update({kk: float(vv) for kk, vv in v.items() if kk in fw})
                    s["factor_weights"] = fw
                elif k in DEFAULT_SETTINGS:
                    s[k] = v
        except (json.JSONDecodeError, OSError):
            pass
    return s


def save_settings(update: dict) -> dict:
    with _lock:
        s = load_settings()
        for k, v in update.items():
            if k not in DEFAULT_SETTINGS or v is None:
                continue
            if k == "lookback_sessions":
                if int(v) not in ALLOWED_LOOKBACKS:
                    raise ValueError(f"lookback_sessions doit être parmi {sorted(ALLOWED_LOOKBACKS)}")
                s[k] = int(v)
            elif k in ("bullish_threshold", "bearish_threshold",
                       "strong_bullish_threshold", "strong_bearish_threshold"):
                s[k] = float(v)
            elif k in ("neutral_band_pct", "strong_band_pct"):
                s[k] = max(0.0, float(v))
            elif k in ("cutoff_paris", "measure_start_ny"):
                h, m = str(v).split(":")
                if not (0 <= int(h) < 24 and 0 <= int(m) < 60):
                    raise ValueError(f"heure invalide: {v}")
                s[k] = f"{int(h):02d}:{int(m):02d}"
            elif k == "factor_weights" and isinstance(v, dict):
                fw = dict(s["factor_weights"])
                fw.update({kk: float(vv) for kk, vv in v.items() if kk in fw})
                s["factor_weights"] = fw
            elif k == "es_provider":
                if v not in ("yahoo", "databento"):
                    raise ValueError("es_provider doit être 'yahoo' ou 'databento'")
                s[k] = v
        if not (s["strong_bearish_threshold"] < s["bearish_threshold"] < 0
                < s["bullish_threshold"] < s["strong_bullish_threshold"]):
            raise ValueError(
                "ordre requis : strong_bearish < bearish < 0 < bullish < strong_bullish")
        if s["strong_band_pct"] <= s["neutral_band_pct"]:
            raise ValueError("strong_band_pct doit être > neutral_band_pct")
        SETTINGS_PATH.write_text(json.dumps(s, indent=2))
        return s


def _load_keys() -> dict[str, str]:
    keys: dict[str, str] = {}
    for path in (BASE_DIR / ".env", KEYS_PATH):
        if path.exists():
            for k, v in dotenv_values(path).items():
                if v:
                    keys[k] = v
    for env_name in KEY_PROVIDERS.values():
        if os.environ.get(env_name):
            keys[env_name] = os.environ[env_name]
    return keys


def get_api_key(provider: str) -> str | None:
    env_name = KEY_PROVIDERS.get(provider)
    if not env_name:
        return None
    return _load_keys().get(env_name)


def set_api_key(provider: str, key: str | None) -> None:
    env_name = KEY_PROVIDERS.get(provider)
    if not env_name:
        raise ValueError(f"fournisseur inconnu: {provider}")
    with _lock:
        stored = dict(dotenv_values(KEYS_PATH)) if KEYS_PATH.exists() else {}
        if key:
            stored[env_name] = key.strip()
        else:
            stored.pop(env_name, None)
        lines = [f"{k}={v}" for k, v in stored.items() if v]
        KEYS_PATH.write_text("\n".join(lines) + ("\n" if lines else ""))
        try:
            KEYS_PATH.chmod(0o600)
        except OSError:
            pass


def mask_key(key: str | None) -> str | None:
    if not key:
        return None
    return "••••" + key[-4:] if len(key) > 4 else "••••"
