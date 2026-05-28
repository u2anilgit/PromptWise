import pytest
from promptwise_v2.plugins.budget_guardian import BudgetGuardian


def test_ok_status_under_50pct():
    guardian = BudgetGuardian(limit_usd=10.0, team_budget_usd=100.0)
    status = guardian.check(used_usd=3.0, days_elapsed=15)
    assert status.alert_level == "ok"
    assert status.pct_used == 30.0


def test_warn_status_over_70pct():
    guardian = BudgetGuardian(limit_usd=10.0, team_budget_usd=100.0)
    status = guardian.check(used_usd=7.5, days_elapsed=15)
    assert status.alert_level == "warn"


def test_critical_status_over_90pct():
    guardian = BudgetGuardian(limit_usd=10.0, team_budget_usd=100.0)
    status = guardian.check(used_usd=9.1, days_elapsed=1)
    assert status.alert_level == "critical"


def test_hard_stop_at_limit():
    guardian = BudgetGuardian(limit_usd=10.0, team_budget_usd=100.0)
    status = guardian.check(used_usd=10.5, days_elapsed=1)
    assert status.alert_level == "hard_stop"


def test_projected_monthly_calculation():
    guardian = BudgetGuardian(limit_usd=10.0, team_budget_usd=100.0)
    status = guardian.check(used_usd=5.0, days_elapsed=10)
    assert status.projected_monthly_usd == pytest.approx(15.0, rel=0.01)


def test_daily_burn_rate():
    guardian = BudgetGuardian(limit_usd=10.0, team_budget_usd=100.0)
    status = guardian.check(used_usd=6.0, days_elapsed=3)
    assert status.daily_burn_usd == pytest.approx(2.0, rel=0.01)
