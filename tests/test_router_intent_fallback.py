"""Regression test for a router bug: _detect_intent()'s no-match fallback used
to return the literal string "auto" -- the same sentinel route() uses to mean
"please detect this" (route(intent="auto", ...)). That collision made
_static_tier() silently treat every undetected prompt as an unknown intent,
falling through to the generic "balanced" tier regardless of actual
complexity (e.g. "Design multi-region event-driven microservices" and
"Fix typo in variable name" routed identically). The fallback is now
"general", a value distinct from the "auto" trigger."""
from promptwise.core.router import Router


def test_unmatched_text_does_not_fall_back_to_the_auto_sentinel():
    router = Router()
    detected = router.detect_intent("Please help me understand this topic better")
    assert detected != "auto"
    assert detected == "general"


def test_route_reports_the_real_detected_intent_not_the_auto_sentinel():
    router = Router()
    result = router.route(text="Design multi-region event-driven microservices",
                           intent="auto", stakes="auto", provider="claude")
    assert result.intent_detected != "auto"


def test_architecture_prompt_detected_as_architecture_intent():
    router = Router()
    assert router.detect_intent("Design multi-region event-driven microservices") == "architecture"
    assert router.detect_intent("Plan the system design for a distributed system") == "architecture"


def test_trivial_prompt_detected_as_trivial_intent():
    router = Router()
    assert router.detect_intent("Fix typo in variable name") == "trivial"


def test_pull_request_no_longer_misclassified_as_extract():
    router = Router()
    # "pull" alone used to match the "extract" bucket via bare substring/word
    # match on "pull request" -- this must now fall through to "code".
    assert router.detect_intent("Review pull request #42 for security flaws") == "code"


def test_architecture_intent_always_routes_to_powerful_tier_regardless_of_stakes():
    router = Router()
    assert router._static_tier("architecture", "low") == "powerful"
    assert router._static_tier("architecture", "medium") == "powerful"
    assert router._static_tier("architecture", "high") == "powerful"


def test_trivial_intent_always_routes_to_fast_tier_regardless_of_stakes():
    router = Router()
    assert router._static_tier("trivial", "low") == "fast"
    assert router._static_tier("trivial", "high") == "fast"


def test_small_and_large_prompts_no_longer_route_identically():
    router = Router()
    small = router.route(text="Fix typo in variable name", intent="auto", stakes="auto", provider="claude")
    big = router.route(text="Design multi-region event-driven microservices",
                        intent="auto", stakes="auto", provider="claude")
    assert small.intent_detected == "trivial"
    assert big.intent_detected == "architecture"
    assert small.recommended_model != big.recommended_model
