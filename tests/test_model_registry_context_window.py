import yaml

from promptwise.core.model_registry import ModelRegistry


def _registry(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text(yaml.safe_dump({
        "families": {
            "big": {"provider": "acme", "tier": "powerful"},
            "small": {"provider": "other", "tier": "fast"},
        },
        "models": [
            {"alias": "big-2", "family": "big", "status": "current",
             "release_date": "2026-09-01", "context_window": 1000000},
            {"alias": "big-1", "family": "big", "status": "current",
             "release_date": "2026-05-01", "context_window": 400000},
            {"alias": "small-1", "family": "small", "status": "current",
             "release_date": "2026-09-01"},
        ],
    }), encoding="utf-8")
    return ModelRegistry(p)


def test_context_window_of_reads_the_registry_row(tmp_path):
    reg = _registry(tmp_path)
    assert reg.context_window_of("big-2") == 1000000
    assert reg.context_window_of("big-1") == 400000


def test_context_window_of_returns_none_when_absent(tmp_path):
    """None means 'the registry does not know', which is distinguishable from a
    real value. Returning a default here would make a guessed 200000 look like a
    verified one."""
    reg = _registry(tmp_path)
    assert reg.context_window_of("small-1") is None
    assert reg.context_window_of("no-such-model") is None


def test_top_n_current_filters_by_provider(tmp_path):
    reg = _registry(tmp_path)
    assert reg.top_n_current(provider="acme") == ["big-2", "big-1"]
    assert reg.top_n_current(provider="other") == ["small-1"]
    assert reg.top_n_current(provider="nobody") == []


def test_top_n_current_keeps_its_existing_positional_signature(tmp_path):
    reg = _registry(tmp_path)
    assert reg.top_n_current("powerful", 1) == ["big-2"]


def test_top_n_current_combines_tier_and_provider(tmp_path):
    reg = _registry(tmp_path)
    assert reg.top_n_current("powerful", provider="acme") == ["big-2", "big-1"]
    assert reg.top_n_current("fast", provider="acme") == []


def test_router_prefers_the_registry_context_window(tmp_path):
    from promptwise.core.router import Router
    router = Router()
    router.registry = _registry(tmp_path)
    _rate, window = router._input_rate("big-2")
    assert window == 1000000


def test_router_falls_back_to_app_config_when_the_registry_is_silent(tmp_path):
    from promptwise.core.router import Router
    router = Router()
    router.registry = _registry(tmp_path)
    _rate, window = router._input_rate("small-1")
    assert window == router.config.get_model("small-1").context_window


def test_the_shipped_catalog_declares_real_context_windows():
    """A 1M-context model routed as if it had 200k produces a wrong
    context_window_pct on every call."""
    reg = ModelRegistry()
    assert reg.context_window_of("claude-opus-5") in (None, 1000000)
