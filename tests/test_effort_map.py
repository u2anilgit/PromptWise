"""effort_map -- per-provider mapping from the internal effort label
(low/medium/high) to the concrete parameter a provider's API expects,
resolved the same way model_registry.resolve() resolves tier -> concrete
model id. Config is the source of truth; built-in defaults are the fallback
when config/effort_map.yaml is absent or malformed."""
from promptwise.core.effort_map import resolve_effort_param


def test_resolve_claude_effort_param_from_config(tmp_path):
    p = tmp_path / "effort_map.yaml"
    p.write_text(
        "providers:\n  claude:\n    low: {thinking_budget_tokens: 999}\n"
        "    medium: {thinking_budget_tokens: 4096}\n    high: {thinking_budget_tokens: 16000}\n"
        "default_provider: claude\n",
        encoding="utf-8",
    )
    assert resolve_effort_param("low", provider="claude", path=p) == {"thinking_budget_tokens": 999}


def test_resolve_falls_back_to_builtin_defaults_when_path_missing(tmp_path):
    missing = tmp_path / "does_not_exist.yaml"
    assert resolve_effort_param("high", provider="claude", path=missing) == {"thinking_budget_tokens": 16000}


def test_resolve_openai_effort_param_from_defaults():
    assert resolve_effort_param("low", provider="openai", path="/nonexistent/path.yaml") == {"reasoning_effort": "low"}


def test_unknown_provider_falls_back_to_default_provider():
    result = resolve_effort_param("medium", provider="unknown-provider", path="/nonexistent/path.yaml")
    assert result == {"thinking_budget_tokens": 4096}


def test_unknown_effort_falls_back_to_medium():
    result = resolve_effort_param("extreme", provider="claude", path="/nonexistent/path.yaml")
    assert result == {"thinking_budget_tokens": 4096}
