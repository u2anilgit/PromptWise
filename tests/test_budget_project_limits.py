from promptwise.plugins.budget import BudgetGuardian


def test_no_project_limit_falls_back_to_global():
    g = BudgetGuardian(limit_usd=100.0)
    status = g.check(used_usd=50.0, days_elapsed=1, project_id="team-a")
    assert status.limit_usd == 100.0


def test_project_specific_limit_used_when_set():
    g = BudgetGuardian(limit_usd=100.0)
    g.set_limit(20.0, project="team-a")

    status = g.check(used_usd=15.0, days_elapsed=1, project_id="team-a")
    assert status.limit_usd == 20.0

    other = g.check(used_usd=15.0, days_elapsed=1, project_id="team-b")
    assert other.limit_usd == 100.0  # unaffected


def test_global_set_limit_still_works_unscoped():
    g = BudgetGuardian(limit_usd=100.0)
    g.set_limit(200.0)
    assert g.limit_usd == 200.0


def test_project_limit_hard_stop_alert():
    g = BudgetGuardian(limit_usd=100.0, mode="block")
    g.set_limit(10.0, project="team-a")

    status = g.check(used_usd=12.0, days_elapsed=1, project_id="team-a")
    assert status.alert_level == "hard_stop"
    assert status.blocked is True
