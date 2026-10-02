"""Drawdown engine (§48-49).

Prop firms differ wildly, so the drawdown *type* is a per-firm input and we
never assume a single 5%/10% model (§48). Supported types (§49): STATIC,
TRAILING, EQUITY_BASED, BALANCE_BASED, DAILY_RESET.

All computations are pure functions of a value series + the firm's rule, so a
new account's numbers can be recomputed in isolation (§73)."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..core.enums import DrawdownType


@dataclass(slots=True)
class DrawdownResult:
    current_dd_pct: float
    max_dd_pct: float
    current_loss: float
    remaining_loss: float | None  # None => rule unknown (§88)
    daily_loss: float
    remaining_daily: float | None


def _peak_series_dd(values: Sequence[float]) -> tuple[float, float]:
    """Return (current_dd_amount_from_peak, max_dd_amount_from_peak)."""
    peak = values[0]
    max_dd = 0.0
    for v in values:
        peak = max(peak, v)
        max_dd = max(max_dd, peak - v)
    current_dd = peak - values[-1]
    return current_dd, max_dd


def compute(
    equity_series: Sequence[float],
    *,
    initial_balance: float,
    dd_type: DrawdownType = DrawdownType.STATIC,
    max_total_loss_pct: float | None = None,
    daily_loss_pct: float | None = None,
    day_start_equity: float | None = None,
) -> DrawdownResult:
    if not equity_series:
        equity_series = [initial_balance]
    current = equity_series[-1]

    if dd_type in (DrawdownType.STATIC, DrawdownType.BALANCE_BASED):
        # Loss measured from the fixed initial baseline.
        current_loss = max(0.0, initial_balance - current)
        base = initial_balance
        current_dd_amount = current_loss
        _, max_dd_amount = _peak_series_dd([initial_balance, *equity_series])
        # static max dd is the worst drop below the initial baseline
        max_dd_amount = max(0.0, initial_balance - min(equity_series))
    else:
        # TRAILING / EQUITY_BASED: measured from the running peak.
        current_dd_amount, max_dd_amount = _peak_series_dd([initial_balance, *equity_series])
        base = max(initial_balance, max(equity_series))
        current_loss = current_dd_amount

    current_dd_pct = round(current_dd_amount / base * 100.0, 2) if base else 0.0
    max_dd_pct = round(max_dd_amount / base * 100.0, 2) if base else 0.0

    remaining_loss: float | None = None
    if max_total_loss_pct is not None:
        limit_amount = initial_balance * max_total_loss_pct / 100.0
        remaining_loss = round(limit_amount - current_loss, 2)

    # Daily loss (§48). DAILY_RESET uses the equity at the start of the day.
    start = day_start_equity if day_start_equity is not None else initial_balance
    daily_loss = round(max(0.0, start - current), 2)
    remaining_daily: float | None = None
    if daily_loss_pct is not None:
        daily_limit = start * daily_loss_pct / 100.0
        remaining_daily = round(daily_limit - daily_loss, 2)

    return DrawdownResult(
        current_dd_pct=current_dd_pct, max_dd_pct=max_dd_pct,
        current_loss=round(current_loss, 2), remaining_loss=remaining_loss,
        daily_loss=daily_loss, remaining_daily=remaining_daily,
    )
