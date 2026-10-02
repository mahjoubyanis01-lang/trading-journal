"""Performance engine (§42-45).

Pure functions over balances/snapshots so they are trivially unit-testable and
cheap to recompute for a single changed account (§73 - never recompute all)."""
from __future__ import annotations

from collections.abc import Iterable


def total_pnl(initial_balance: float, balance: float) -> float:
    return round(balance - initial_balance, 2)


def performance_pct(initial_balance: float, balance: float) -> float:
    if initial_balance <= 0:
        return 0.0
    return round((balance - initial_balance) / initial_balance * 100.0, 2)


def sum_pnl(records: Iterable[float]) -> float:
    return round(sum(records), 2)


def monthly_performance_pct(initial_balance: float, month_pnl: float) -> float:
    if initial_balance <= 0:
        return 0.0
    return round(month_pnl / initial_balance * 100.0, 2)


def aggregate_capital(initial_balances: Iterable[float]) -> float:
    """Capital managed = sum of account initial balances (§40-41)."""
    return round(sum(initial_balances), 2)
