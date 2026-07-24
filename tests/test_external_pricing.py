"""Advisory cross-provider cost comparison -- see
docs/superpowers/specs/2026-07-24-cross-provider-routing-design.md.
"""
from promptwise.core.external_pricing import ExternalPricingCatalog
from promptwise.core.router import Router


def test_catalog_loads_bundled_reference_pricing():
    cat = ExternalPricingCatalog()
    assert cat.loaded is True
    assert len(cat.all()) >= 1
    for m in cat.all():
        assert m["provider"] and m["model"]
        assert m["input_per_mtok"] is not None
        assert m["output_per_mtok"] is not None


def test_catalog_for_tier_filters_correctly():
    cat = ExternalPricingCatalog()
    fast = cat.for_tier("fast")
    assert all(m["tier"] == "fast" for m in fast)
    assert len(fast) >= 1


def test_catalog_missing_file_is_fail_open(tmp_path):
    cat = ExternalPricingCatalog(tmp_path / "does_not_exist.yaml")
    assert cat.loaded is False
    assert cat.all() == []


def test_compare_providers_claude_entry_is_not_advisory():
    router = Router()
    results = router.compare_providers("hello world", model="claude-sonnet-4-6")
    claude_entries = [r for r in results if r["provider"] == "claude"]
    assert len(claude_entries) == 1
    assert claude_entries[0]["advisory"] is False
    assert claude_entries[0]["total_cost_usd"] > 0


def test_compare_providers_includes_external_by_default():
    router = Router()
    results = router.compare_providers("hello world", model="claude-sonnet-4-6")
    external = [r for r in results if r["advisory"] is True]
    assert len(external) >= 1
    for r in external:
        assert r["provider"] != "claude"
        assert r["total_cost_usd"] > 0
        assert "note" in r


def test_compare_providers_can_exclude_external():
    router = Router()
    results = router.compare_providers("hello world", model="claude-sonnet-4-6", include_external=False)
    assert len(results) == 1
    assert results[0]["provider"] == "claude"


def test_external_models_never_leak_into_actual_routing():
    """The whole point of keeping this catalog decoupled: adding external,
    non-'current'-status reference pricing must never make route() or the
    registry's selectable-model helpers surface an openai/gemini alias --
    the ones this feature actually adds to the system (a machine-local
    on-device model overlay is a separate, pre-existing feature and is not
    what this assertion is guarding against)."""
    router = Router()
    result = router.route("write a function")
    assert result.recommended_model not in ("gpt-4o", "gpt-4o-mini", "gemini-2.0-flash", "gemini-1.5-pro")
    assert not any(a in ("gpt-4o", "gpt-4o-mini", "gemini-2.0-flash", "gemini-1.5-pro") for a in result.alternatives)
    assert not any(m in ("gpt-4o", "gpt-4o-mini", "gemini-2.0-flash", "gemini-1.5-pro") for m in router._current_models())
