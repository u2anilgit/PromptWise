"""Router.route() accepted monthly_budget_usd/days_elapsed_in_month but never
read them -- budget-aware routing only ever worked via provider_spend_usd's
hard daily cap. Projected monthly spend at the reported burn rate
(provider_spend_usd / days_elapsed_in_month * 30) must now reroute to the
fast tier when it would exceed monthly_budget_usd, same formula
BudgetGuardian.check() already uses for daily_burn -> projected_monthly.
"""
from promptwise.config import AppConfig
from promptwise.core.router import Router


def test_no_monthly_budget_params_never_caps():
    r = Router(AppConfig())
    res = r.route("write a function", intent="code", stakes="high", provider="claude")
    assert res.monthly_budget_capped is False


def test_projected_pace_under_budget_routes_normally():
    r = Router(AppConfig())
    res = r.route("Design a critical production security architecture", intent="analysis",
                  stakes="high", provider="claude",
                  monthly_budget_usd=100.0, days_elapsed_in_month=10, provider_spend_usd=10.0)
    assert res.monthly_budget_capped is False
    assert res.recommended_model != "claude-haiku-4-5-20251001"


def test_projected_pace_over_budget_reroutes_to_fast_tier():
    r = Router(AppConfig())
    res = r.route("Design a critical production security architecture", intent="analysis",
                  stakes="high", provider="claude",
                  monthly_budget_usd=50.0, days_elapsed_in_month=1, provider_spend_usd=10.0)
    assert res.monthly_budget_capped is True
    assert res.recommended_model == "claude-haiku-4-5-20251001"
    assert "monthly_budget_usd" in res.reason
