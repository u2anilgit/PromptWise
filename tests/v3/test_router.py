"""Tests for unified V3 Router."""

from promptwise_v3.core.router import Router


def test_route_code_intent(router: Router):
    result = router.route(text="Write a Python function to sort a list")
    assert result.intent_detected == "code"
    assert result.recommended_model == "claude-sonnet-4-6"


def test_route_high_stakes_opus(router: Router):
    result = router.route(text="Implement a critical security architecture for customer production system", stakes="high")
    assert result.recommended_model == "claude-opus-4-7"


def test_route_low_stakes_haiku(router: Router):
    result = router.route(text="Summarize the team standup notes", stakes="low")
    assert result.recommended_model == "claude-haiku-4-5-20251001"


def test_route_intent_analysis(router: Router):
    result = router.route(text="Analyze this dataset and generate a report")
    assert result.intent_detected == "analysis"


def test_route_intent_extract(router: Router):
    result = router.route(text="Extract all email addresses from this document")
    assert result.intent_detected == "extract"
    assert result.batch_recommended is True


def test_route_intent_classify(router: Router):
    result = router.route(text="Classify these support tickets by priority")
    assert result.batch_recommended is True


def test_route_alternatives(router: Router):
    result = router.route(text="Fix this bug in the login flow")
    alt = result.alternatives
    assert result.recommended_model not in alt
    assert len(alt) == 2


def test_compare_providers(router: Router):
    results = router.compare_providers("Hello world", model="claude-sonnet-4-6")
    assert len(results) == 1
    assert results[0]["provider"] == "claude"
    assert results[0]["total_cost_usd"] > 0


def test_resolve_model_budget_over_95(router: Router):
    model = router.resolve_model("any-skill", budget_pct=96.0)
    assert model == "claude-haiku-4-5-20251001"


def test_resolve_model_budget_over_80(router: Router):
    model = router.resolve_model("any-skill", budget_pct=85.0)
    assert model == "claude-sonnet-4-6"


def test_route_for_plugin_monitoring(router: Router):
    plugin = router.route_for_plugin("Monitor the budget and track costs")
    assert plugin == "monitoring"


def test_route_for_plugin_none(router: Router):
    plugin = router.route_for_plugin("Write a haiku about programming")
    assert plugin is None


def test_route_empty_string(router: Router):
    result = router.route(text="")
    assert result.intent_detected == "auto"


def test_fallback_models_excludes_current(router: Router):
    models = router.fallback_models(current="claude-sonnet-4-6")
    assert "claude-sonnet-4-6" not in models
    assert len(models) == 2
