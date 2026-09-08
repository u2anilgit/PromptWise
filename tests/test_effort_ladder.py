from promptwise.core.effort_map import nearest_supported, resolve_effort_param
from promptwise.core.effort_router import EFFORT_ORDER, static_effort


def test_ladder_spans_none_to_xhigh():
    assert EFFORT_ORDER == ("none", "low", "medium", "high", "xhigh")


def test_existing_two_argument_calls_are_unchanged():
    assert static_effort("extract", "low") == "low"
    assert static_effort("code", "high") == "high"
    assert static_effort("code", "medium") == "medium"
    assert static_effort("question", "low") == "low"


def test_trivial_task_types_reach_the_none_rung():
    assert static_effort("extract", "low", task_type="docs") == "none"


def test_high_stakes_bugfix_reaches_xhigh():
    assert static_effort("code", "high", task_type="bugfix") == "xhigh"
    assert static_effort("code", "high", task_type="refactor") == "xhigh"
    assert static_effort("code", "high", task_type="docs") == "high"


def test_nearest_supported_clamps_down_and_up():
    assert nearest_supported("xhigh", ["low", "medium", "high"]) == "high"
    assert nearest_supported("none", ["low", "medium", "high"]) == "low"
    assert nearest_supported("medium", ["low", "medium", "high"]) == "medium"
    assert nearest_supported("medium", []) == "medium"


def test_a_clamp_tie_resolves_downward():
    """Ties must not silently cost more than the caller asked for."""
    assert nearest_supported("medium", ["low", "high"]) == "low"


def test_every_configured_provider_resolves_a_param_for_every_rung():
    for provider in ("claude", "openai", "gemini", "xai"):
        for effort in EFFORT_ORDER:
            param = resolve_effort_param(effort, provider)
            assert isinstance(param, dict) and param, (provider, effort)


def test_providers_that_cannot_disable_reasoning_clamp_none_upward():
    """xAI reasoning cannot be turned off, so `none` must resolve to its
    cheapest real rung rather than dropping the parameter."""
    assert resolve_effort_param("none", "xai") == {"reasoning_effort": "low"}


def test_gemini_uses_a_level_enum_not_a_token_budget():
    param = resolve_effort_param("high", "gemini")
    assert "thinking_level" in param
    assert "thinking_budget" not in param


def test_unknown_provider_falls_back_to_the_default_provider():
    assert resolve_effort_param("high", "no-such-provider") == resolve_effort_param("high", "claude")
