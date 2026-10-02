"""Drawdown engine tests (§48-49)."""
from app.core.enums import DrawdownType
from app.performance import drawdown


def test_static_drawdown_from_initial():
    # initial 10 000, dips to 9 600 then 9 800 now
    res = drawdown.compute(
        [10_000, 9_600, 9_800], initial_balance=10_000,
        dd_type=DrawdownType.STATIC, max_total_loss_pct=10.0,
    )
    assert res.current_loss == 200.0  # 10000 - 9800
    assert res.current_dd_pct == 2.0
    assert res.max_dd_pct == 4.0  # worst dip 10000 - 9600
    # remaining to a 10% (=1000) limit, already lost 200 => 800 left
    assert res.remaining_loss == 800.0


def test_trailing_drawdown_from_peak():
    # climbs to 10 800 (peak) then falls to 10 500
    res = drawdown.compute(
        [10_000, 10_800, 10_500], initial_balance=10_000,
        dd_type=DrawdownType.TRAILING,
    )
    # current dd from peak 10 800 => 300
    assert res.current_loss == 300.0
    assert res.current_dd_pct > 0


def test_daily_loss_and_remaining():
    res = drawdown.compute(
        [10_000, 9_900], initial_balance=10_000, dd_type=DrawdownType.DAILY_RESET,
        daily_loss_pct=5.0, day_start_equity=10_000,
    )
    assert res.daily_loss == 100.0
    assert res.remaining_daily == 400.0  # 5% = 500 limit, lost 100


def test_unknown_rule_leaves_remaining_none():
    # §88 : no rule provided => remaining stays None, never fabricated
    res = drawdown.compute([10_000, 9_900], initial_balance=10_000)
    assert res.remaining_loss is None
    assert res.remaining_daily is None
