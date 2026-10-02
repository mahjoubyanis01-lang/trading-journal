"""Risk engine tests (§32-39, Acceptance Tests 2 & 3)."""
from app.connectors.base import InstrumentInfo
from app.core.enums import AssetClass, RiskMode, RiskReference
from app.risk.engine import (
    check_risk_guard,
    compute_volume,
    initial_risk_money,
    resolve_effective_risk,
)


def test_initial_risk_money():
    # §32 : 10 000 x 0.5% = 50 $
    assert initial_risk_money(10_000, 0.5) == 50.0


def test_fixed_money_stays_fixed_when_balance_grows():
    # §33 : balance 10 000 -> 10 800, risk stays 50 $
    r = resolve_effective_risk(
        account_mode=None, account_amount=None, account_percent=None, account_reference=None,
        strategy_mode=RiskMode.FIXED_MONEY, strategy_percent=0.5,
        strategy_reference=RiskReference.INITIAL_BALANCE,
        initial_balance=10_000, current_balance=10_800, equity=10_795,
    )
    assert r.mode == RiskMode.FIXED_MONEY
    assert r.amount == 50.0  # not 54
    assert r.source == "inherited"


def test_dynamic_percent_follows_balance():
    # §34 : 0.5% of current balance
    r = resolve_effective_risk(
        account_mode=RiskMode.DYNAMIC_PERCENT, account_amount=None, account_percent=0.5,
        account_reference=RiskReference.CURRENT_BALANCE,
        strategy_mode=RiskMode.FIXED_MONEY, strategy_percent=0.5,
        strategy_reference=RiskReference.INITIAL_BALANCE,
        initial_balance=10_000, current_balance=10_800, equity=10_800,
    )
    assert r.mode == RiskMode.DYNAMIC_PERCENT
    assert r.amount == 54.0
    assert r.source == "override"


def test_account_override_amount():
    # §35 : user edits 50 -> 75
    r = resolve_effective_risk(
        account_mode=RiskMode.FIXED_MONEY, account_amount=75.0, account_percent=None,
        account_reference=None,
        strategy_mode=RiskMode.FIXED_MONEY, strategy_percent=0.5,
        strategy_reference=RiskReference.INITIAL_BALANCE,
        initial_balance=10_000, current_balance=10_000, equity=10_000,
    )
    assert r.amount == 75.0
    assert r.source == "override"


def _eurusd() -> InstrumentInfo:
    return InstrumentInfo(
        "EURUSDm", "Euro vs USD", AssetClass.FOREX, "EUR", "USD",
        contract_size=100_000, tick_size=0.00001, tick_value=1.0,
        volume_min=0.01, volume_max=100.0, volume_step=0.01, digits=5,
    )


def test_volume_from_money_risk():
    # risk 50 $, SL 20 pips = 0.0020 ; loss/lot = (0.0020/0.00001)*1 = 200
    # volume = 50/200 = 0.25 lot, est loss = 50
    res = compute_volume(50.0, 0.0020, _eurusd())
    assert res.ok
    assert res.volume == 0.25
    assert res.estimated_loss == 50.0


def test_volume_normalises_down_to_step():
    # risk 55 $ -> 0.275 -> floored to step 0.01 -> 0.27
    res = compute_volume(55.0, 0.0020, _eurusd())
    assert res.ok
    assert res.volume == 0.27
    assert res.estimated_loss <= 55.0  # never exceeds requested after flooring


def test_volume_unknown_specs_refuses():
    # §88 : missing tick_value => UNKNOWN, no guessing
    inst = InstrumentInfo("WEIRD", tick_size=0.1, tick_value=None)
    res = compute_volume(50.0, 1.0, inst)
    assert not res.ok
    assert "UNKNOWN" in res.reason


def test_volume_minimum_lot_warns_when_over_risk():
    inst = _eurusd()
    # tiny risk that can't be met even by the minimum lot
    res = compute_volume(0.5, 0.0020, inst)
    assert res.ok
    assert res.volume == 0.01
    assert res.warnings  # flagged that min lot exceeds requested risk


def test_risk_guard_flags_incoherent():
    # §39 : risk 5000 on a 10 000 account => needs confirmation
    g = check_risk_guard(5000, 10_000, 0.10)
    assert g.allowed
    assert g.needs_confirmation
    assert g.warnings


def test_risk_guard_ok_for_normal_risk():
    g = check_risk_guard(50, 10_000, 0.10)
    assert g.allowed
    assert not g.needs_confirmation
