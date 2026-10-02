"""Performance engine tests (§42-43)."""
from app.performance import engine


def test_total_pnl_and_pct():
    assert engine.total_pnl(10_000, 10_842) == 842.0
    assert engine.performance_pct(10_000, 10_842) == 8.42


def test_monthly_performance():
    assert engine.monthly_performance_pct(10_000, 842) == 8.42


def test_sum_daily():
    assert engine.sum_pnl([82, 174, -120, 310]) == 446.0


def test_capital_aggregate():
    assert engine.aggregate_capital([10_000, 20_000, 50_000, 100_000]) == 180_000.0


def test_zero_initial_is_safe():
    assert engine.performance_pct(0, 500) == 0.0
