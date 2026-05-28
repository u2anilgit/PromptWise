from promptwise_v2.core.router_v2 import RouterV2

router = RouterV2()

def test_route_for_plugin_monitoring():
    plugin = router.route_for_plugin("Track cost and burn rate for this session")
    assert plugin == "monitoring"

def test_route_for_plugin_codereview():
    plugin = router.route_for_plugin("Review my Python file auth.py for issues")
    assert plugin == "codereview_bridge"

def test_route_for_plugin_playwright():
    plugin = router.route_for_plugin("Test the React component visually")
    assert plugin == "playwright_bridge"

def test_route_for_plugin_none():
    plugin = router.route_for_plugin("Summarize this meeting notes")
    assert plugin is None

def test_fallback_models_sequence():
    models = router.fallback_models(current="claude-opus-4-7")
    assert "claude-sonnet-4-6" in models
    assert "claude-haiku-4-5-20251001" in models

def test_fallback_excludes_current():
    models = router.fallback_models(current="claude-sonnet-4-6")
    assert "claude-sonnet-4-6" not in models
