"""Global Trading Hub configuration (§74-75).

Values come from environment variables (prefix ``TH_``) with sane defaults.
The *operational* defaults a user edits in the UI (default risk, thresholds,
auto-start, ...) live in the ``settings`` table so they can change at runtime;
this object holds the process-level, boot-time configuration.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from .enums import RiskMode, RiskReference

# Repo-local data dir by default; on Windows the agent points this at %APPDATA%.
_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TH_", env_file=".env", extra="ignore")

    app_name: str = "Trading Hub"
    data_dir: Path = _DEFAULT_DATA_DIR
    database_url: str = ""  # filled from data_dir if empty

    # Mock mode lets the whole stack run with a simulated platform (§70).
    mock_mode: bool = True

    # --- operational defaults (also mirrored into the settings table) ---
    default_risk_percent: float = 0.5
    default_risk_mode: RiskMode = RiskMode.FIXED_MONEY
    default_risk_reference: RiskReference = RiskReference.INITIAL_BALANCE

    # Market mapping confidence thresholds (§26, configurable).
    confidence_auto: float = 90.0
    confidence_confirm: float = 70.0

    # Risk safety guard: warn when risk/position exceeds this share of capital (§39).
    risk_warn_fraction: float = 0.10

    # Heartbeat timeout in seconds before a robot is considered lost (§66).
    heartbeat_timeout_s: int = 60
    # How often the monitor loop ticks.
    monitor_interval_s: int = 5
    # Max auto-recovery attempts before giving up (§51).
    recovery_max_attempts: int = 3

    monitor_enabled: bool = True  # disabled in tests for determinism
    auto_start: bool = True
    auto_recovery: bool = True
    market_discovery: bool = True
    auto_mapping: bool = True

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.data_dir / 'trading_hub.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
