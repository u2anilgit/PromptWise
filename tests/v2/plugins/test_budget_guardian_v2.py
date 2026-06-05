"""Extended tests for BudgetGuardian: project_id param and cost_anomaly_detect."""
import pytest
from promptwise_v2.plugins.budget_guardian import BudgetGuardian


# ---------------------------------------------------------------------------
# check() with project_id
# ---------------------------------------------------------------------------

def test_check_with_project_id_returns_project_id_in_result():
    guardian = BudgetGuardian(limit_usd=10.0, team_budget_usd=100.0)
    status = guardian.check(used_usd=3.0, days_elapsed=5, project_id="proj-abc")
    assert status.project_id == "proj-abc"
    assert status.alert_level == "ok"


def test_check_without_project_id_still_works():
    guardian = BudgetGuardian(limit_usd=10.0, team_budget_usd=100.0)
    status = guardian.check(used_usd=5.0, days_elapsed=10)
    assert status.project_id is None
    assert status.alert_level == "ok"


# ---------------------------------------------------------------------------
# cost_anomaly_detect
# ---------------------------------------------------------------------------

def test_anomaly_detect_alert_when_latest_exceeds_2x_avg():
    guardian = BudgetGuardian()
    # window (last 7 excluding latest): [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] → avg=1.0
    # latest = 3.0 → 3.0 > 2 * 1.0 → alert
    daily_costs = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 3.0]
    result = guardian.cost_anomaly_detect(daily_costs)
    assert result["alert"] is True
    assert result["latest"] == 3.0
    assert result["avg_7d"] == pytest.approx(1.0)


def test_anomaly_detect_no_alert_when_latest_within_2x_avg():
    guardian = BudgetGuardian()
    # window (last 7 excluding latest): [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] → avg=1.0
    # latest = 1.5 → 1.5 <= 2.0 → no alert
    daily_costs = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.5]
    result = guardian.cost_anomaly_detect(daily_costs)
    assert result["alert"] is False
    assert result["latest"] == 1.5
    assert result["avg_7d"] == pytest.approx(1.0)


def test_anomaly_detect_empty_list_no_crash():
    guardian = BudgetGuardian()
    result = guardian.cost_anomaly_detect([])
    assert result["alert"] is False
    assert result["latest"] == 0.0
    assert result["avg_7d"] == 0.0


def test_anomaly_detect_single_entry_edge_case():
    guardian = BudgetGuardian()
    result = guardian.cost_anomaly_detect([5.0])
    assert result["alert"] is False
    assert result["latest"] == 5.0
    # avg_7d is the single entry itself
    assert result["avg_7d"] == pytest.approx(5.0)


def test_anomaly_detect_exactly_2x_avg_is_not_alert():
    """Boundary: latest == 2x avg should NOT trigger alert (strictly greater than)."""
    guardian = BudgetGuardian()
    # window: [1.0, 1.0, 1.0] → avg=1.0; latest=2.0 → NOT > 2.0
    daily_costs = [1.0, 1.0, 1.0, 2.0]
    result = guardian.cost_anomaly_detect(daily_costs)
    assert result["alert"] is False


def test_anomaly_detect_uses_at_most_7_day_window():
    guardian = BudgetGuardian()
    # Long history, only last 7 of the window (excluding latest) matter
    # older entries: [100.0, 100.0, 100.0] (should be ignored)
    # window entries: [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    # latest: 3.0 → avg of window=1.0 → alert
    daily_costs = [100.0, 100.0, 100.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 3.0]
    result = guardian.cost_anomaly_detect(daily_costs)
    assert result["alert"] is True
    assert result["avg_7d"] == pytest.approx(1.0)
