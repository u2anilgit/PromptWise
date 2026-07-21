"""Reasoning-effort (low/medium/high), independent of model tier -- this axis
does not exist anywhere in PromptWise today. static_effort mirrors
router.py's _static_tier shape: same signals (intent, stakes), a second,
independent decision table."""
from promptwise.core.effort_router import EFFORT_ORDER, static_effort


def test_high_stakes_is_always_high_effort_regardless_of_intent():
    assert static_effort("extract", "high") == "high"
    assert static_effort("code", "high") == "high"


def test_low_stakes_cheap_intent_is_low_effort():
    assert static_effort("summarize", "low") == "low"
    assert static_effort("question", "low") == "low"


def test_everything_else_defaults_to_medium():
    assert static_effort("code", "medium") == "medium"
    assert static_effort("analysis", "low") == "medium"


def test_effort_order_is_low_to_high():
    assert EFFORT_ORDER == ("low", "medium", "high")
