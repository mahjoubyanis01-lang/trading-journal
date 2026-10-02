"""Risk engine (§31-39, §90).

Core principles:
- Risk is money, not a bare percentage. The default mode is FIXED_MONEY; the
  percentage only seeds the initial monetary amount from a reference balance
  (§31-33). The robot receives RISK_MODE + RISK_AMOUNT (§32).
- DYNAMIC_PERCENT re-computes the amount from current balance, and is opt-in
  (§34).
- Volume is derived from the *real* instrument specs; if any required spec is
  unknown, we refuse to size and return UNKNOWN rather than guess (§38, §88).
- Safety guards flag incoherent configs (risk too large vs capital) (§39).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..connectors.base import InstrumentInfo
from ..core.enums import RiskMode, RiskReference


@dataclass(slots=True)
class EffectiveRisk:
    mode: RiskMode
    amount: float
    percent: float
    reference: RiskReference
    reference_value: float
    source: str  # "inherited" | "override"


@dataclass(slots=True)
class VolumeResult:
    ok: bool
    volume: float | None
    estimated_loss: float | None
    loss_per_lot: float | None
    reason: str
    warnings: list[str] = field(default_factory=list)


def initial_risk_money(reference_balance: float, percent: float) -> float:
    """§32: 10 000 x 0.5% = 50 $."""
    return round(reference_balance * percent / 100.0, 2)


def resolve_effective_risk(
    *,
    account_mode: RiskMode | None,
    account_amount: float | None,
    account_percent: float | None,
    account_reference: RiskReference | None,
    strategy_mode: RiskMode,
    strategy_percent: float,
    strategy_reference: RiskReference,
    initial_balance: float,
    current_balance: float,
    equity: float,
) -> EffectiveRisk:
    """Apply account-over-strategy inheritance (§59) and compute the money
    amount for the active mode (§33-34).

    Mode/reference may arrive as plain strings (SQLAlchemy String columns) or as
    enums; both are coerced so callers never have to care."""
    def as_mode(v):
        return None if v is None else RiskMode(v)

    def as_ref(v):
        return None if v is None else RiskReference(v)

    account_mode = as_mode(account_mode)
    account_reference = as_ref(account_reference)
    strategy_mode = as_mode(strategy_mode)
    strategy_reference = as_ref(strategy_reference)

    overridden = account_mode is not None or account_amount is not None or account_percent is not None
    mode = account_mode or strategy_mode
    percent = account_percent if account_percent is not None else strategy_percent
    reference = account_reference or strategy_reference

    ref_value = {
        RiskReference.INITIAL_BALANCE: initial_balance,
        RiskReference.CURRENT_BALANCE: current_balance,
        RiskReference.EQUITY: equity,
    }[reference]

    if mode == RiskMode.FIXED_MONEY:
        # Fixed money: explicit amount if set, else seed from percent of ref.
        amount = account_amount if account_amount is not None else initial_risk_money(ref_value, percent)
    else:  # DYNAMIC_PERCENT: always recompute from current balance (§34)
        amount = initial_risk_money(current_balance, percent)

    return EffectiveRisk(
        mode=mode, amount=round(amount, 2), percent=percent, reference=reference,
        reference_value=ref_value, source="override" if overridden else "inherited",
    )


def _floor_to_step(value: float, step: float) -> float:
    steps = math.floor(round(value / step, 9))
    return round(steps * step, 10)


def compute_volume(
    risk_amount: float, sl_distance: float, inst: InstrumentInfo
) -> VolumeResult:
    """Convert a money risk into a validated lot size using real specs (§38).

    sl_distance is in price units (e.g. 0.0020 for 20 pips on EURUSD)."""
    if risk_amount <= 0:
        return VolumeResult(False, None, None, None, "risk amount must be > 0")
    if sl_distance <= 0:
        return VolumeResult(False, None, None, None, "stop-loss distance must be > 0")

    # Required specs - never guess (§88).
    missing = [
        n for n, v in (
            ("tick_size", inst.tick_size),
            ("tick_value", inst.tick_value),
            ("volume_step", inst.volume_step),
            ("volume_min", inst.volume_min),
        ) if v is None or v == 0
    ]
    if "tick_size" in missing or "tick_value" in missing:
        return VolumeResult(False, None, None, None,
                            f"UNKNOWN instrument specs: {', '.join(missing)}")

    loss_per_lot = (sl_distance / inst.tick_size) * inst.tick_value
    if loss_per_lot <= 0:
        return VolumeResult(False, None, None, None, "invalid loss-per-lot computation")

    raw_volume = risk_amount / loss_per_lot
    step = inst.volume_step or 0.01
    vmin = inst.volume_min or step
    vmax = inst.volume_max

    volume = _floor_to_step(raw_volume, step)
    warnings: list[str] = []

    if volume < vmin:
        # The smallest tradable lot already risks more than requested.
        est_min_loss = vmin * loss_per_lot
        warnings.append(
            f"minimum lot {vmin} risks {round(est_min_loss, 2)} (> requested {risk_amount})"
        )
        volume = vmin
    if vmax is not None and volume > vmax:
        warnings.append(f"capped at maximum volume {vmax}")
        volume = _floor_to_step(vmax, step)

    estimated_loss = round(volume * loss_per_lot, 2)
    return VolumeResult(
        ok=True, volume=round(volume, 8), estimated_loss=estimated_loss,
        loss_per_lot=round(loss_per_lot, 6), reason="ok", warnings=warnings,
    )


@dataclass(slots=True)
class RiskGuard:
    allowed: bool
    needs_confirmation: bool
    warnings: list[str]


def check_risk_guard(risk_amount: float, capital: float, warn_fraction: float) -> RiskGuard:
    """§39: block/confirm obviously incoherent risk settings."""
    warnings: list[str] = []
    needs_confirmation = False
    allowed = True
    if capital <= 0:
        return RiskGuard(False, False, ["capital is zero or unknown"])
    frac = risk_amount / capital
    if frac >= 0.5:
        warnings.append(f"risk is {round(frac * 100)}% of capital - extremely high")
        needs_confirmation = True
    elif frac >= warn_fraction:
        warnings.append(f"risk is {round(frac * 100)}% of capital (> {round(warn_fraction * 100)}%)")
        needs_confirmation = True
    if risk_amount <= 0:
        allowed = False
        warnings.append("risk must be positive")
    return RiskGuard(allowed, needs_confirmation, warnings)
