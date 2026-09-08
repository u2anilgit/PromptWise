from promptwise.core.effort_router import EFFORT_ORDER
from promptwise.core.preflight import run_preflight


def test_preflight_surfaces_an_effort_recommendation():
    res = run_preflight("Fix the null-pointer crash in the payment reconciliation job. "
                        "This is production and customers are affected.")
    assert res.recommended_effort in EFFORT_ORDER
    assert isinstance(res.effort_param, dict)
    assert res.effort_param, "a recommended effort with no provider parameter is not actionable"


def test_a_high_stakes_bugfix_reaches_the_top_rung():
    res = run_preflight("Urgent: fix the production crash in the billing service, "
                        "customers are affected and revenue is at risk.")
    assert res.recommended_effort in ("high", "xhigh")


def test_the_default_rung_is_not_announced():
    """medium is the default -- saying so on every prompt is pure noise and a
    token cost paid on every single turn."""
    res = run_preflight("Refactor this helper to be a little clearer.")
    if res.recommended_effort == "medium":
        assert not any("reasoning effort" in n for n in res.notes)


def test_a_non_default_rung_is_announced_with_its_provider_parameter():
    res = run_preflight("Urgent production crash in billing, customers affected, revenue at risk.")
    if res.recommended_effort != "medium":
        note = next((n for n in res.notes if "reasoning effort" in n), "")
        assert res.recommended_effort in note
        assert "=" in note, "the note should carry the concrete provider parameter"


def test_preflight_still_returns_a_result_for_empty_input():
    res = run_preflight("")
    assert res.recommended_effort == ""
    assert res.effort_param == {}
