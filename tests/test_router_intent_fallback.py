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
    detected = router.detect_intent("Design multi-region event-driven microservices")
    assert detected != "auto"
    assert detected == "general"


def test_route_reports_the_real_detected_intent_not_the_auto_sentinel():
    router = Router()
    result = router.route(text="Design multi-region event-driven microservices",
                           intent="auto", stakes="auto", provider="claude")
    assert result.intent_detected != "auto"
