"""Tests for BudgetGuardian."""

import pytest
from promptwise_v3.plugins.budget import BudgetGuardian


def test_ok_status_under_50pct():
    g = BudgetGuardian(limit_usd=10.0)
    s = g.check(used_usd=3.0, days_elapsed=15)
    assert s.alert_level == "ok"
    assert s.pct_used == 30.0


def test_warn_status_over_70pct():
    g = BudgetGuardian(limit_usd=10.0)
    s = g.check(used_usd=7.5, days_elapsed=15)
    assert s.alert_level == "warn"


def test_critical_over_90pct():
    g = BudgetGuardian(limit_usd=10.0)
    s = g.check(used_usd=9.1, days_elapsed=1)
    assert s.alert_level == "critical"


def test_hard_stop_at_limit():
    g = BudgetGuardian(limit_usd=10.0)
    s = g.check(used_usd=10.5, days_elapsed=1)
    assert s.alert_level == "hard_stop"


def test_projected_monthly():
    g = BudgetGuardian(limit_usd=10.0)
    s = g.check(used_usd=5.0, days_elapsed=10)
    assert s.projected_monthly_usd == pytest.approx(15.0, rel=0.01)


def test_set_limit():
    g = BudgetGuardian(limit_usd=10.0)
    g.set_limit(50.0, period="monthly")
    assert g.limit_usd == 50.0


def test_get_budget_status():
    g = BudgetGuardian(limit_usd=10.0)
    s = g.get_budget_status()
    assert s["limit_usd"] == 10.0


def test_predict_cost():
    g = BudgetGuardian()
    r = g.predict_cost("Hello" * 100, model="haiku")
    assert r["estimated_cost_usd"] > 0
    assert "haiku" in r["recommendation"]


def test_predict_cost_high():
    g = BudgetGuardian(limit_usd=0.001)
    r = g.predict_cost("x" * 1000, model="opus")
    assert r["estimated_cost_usd"] > 0


def test_cost_anomaly_no_data():
    g = BudgetGuardian()
    r = g.cost_anomaly_detect([])
    assert r["alert"] is False


def test_cost_anomaly_detected():
    g = BudgetGuardian()
    r = g.cost_anomaly_detect([0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 1.0])
    assert r["alert"] is True


def test_cost_anomaly_normal():
    g = BudgetGuardian()
    r = g.cost_anomaly_detect([0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.15])
    assert r["alert"] is False
