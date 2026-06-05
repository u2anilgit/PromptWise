"""Tests for RouterV2 — covers both original methods and the new
resolve_model / apply_context_routing methods added in v3/phase-0."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from promptwise_v2.core.router_v2 import (
    DEFAULT_MODEL,
    HAIKU_MODEL,
    OPUS_MODEL,
    RouterV2,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def router():
    """Router loaded from the real config/model_strategy.yaml."""
    return RouterV2()


@pytest.fixture()
def router_no_config(tmp_path):
    """Router initialised with a non-existent config — must fall back to defaults."""
    missing = tmp_path / "does_not_exist.yaml"
    return RouterV2(config_path=missing)


@pytest.fixture()
def router_custom(tmp_path):
    """Router loaded from a minimal inline YAML written to a temp file."""
    yaml_text = textwrap.dedent("""\
        default_model: claude-sonnet-4-6

        routing_rules:
          opus:
            skills: [system-design, security-architecture]
          haiku:
            skills: [ping_session, changelog-generator]
          sonnet:
            skills: [code-review, tdd]

        cost_safety:
          downgrade_at_budget_pct: 80
          emergency_haiku_pct: 95
          hard_stop_pct: 100
          never_downgrade:
            - security-architecture

        context_routing:
          large_context_threshold: 50000
          large_context_model: claude-sonnet-4-6
    """)
    cfg = tmp_path / "strategy.yaml"
    cfg.write_text(yaml_text, encoding="utf-8")
    return RouterV2(config_path=cfg)


# ---------------------------------------------------------------------------
# 1. resolve_model — opus skill → opus model
# ---------------------------------------------------------------------------

def test_resolve_model_opus_skill(router):
    model = router.resolve_model("systematic-debugging", budget_pct=0.0)
    assert model == OPUS_MODEL


# ---------------------------------------------------------------------------
# 2. resolve_model — haiku skill → haiku model
# ---------------------------------------------------------------------------

def test_resolve_model_haiku_skill(router):
    model = router.resolve_model("ping_session", budget_pct=0.0)
    assert model == HAIKU_MODEL


# ---------------------------------------------------------------------------
# 3. resolve_model at 85% budget → downgrade opus→sonnet (not never_downgrade)
# ---------------------------------------------------------------------------

def test_resolve_model_downgrade_opus_to_sonnet(router):
    # "agent-chain-designer" is in opus tier but NOT in never_downgrade
    model = router.resolve_model("agent-chain-designer", budget_pct=85.0)
    assert model == DEFAULT_MODEL  # opus was downgraded to sonnet


# ---------------------------------------------------------------------------
# 4. resolve_model for never_downgrade skill at 85% budget → stays opus
# ---------------------------------------------------------------------------

def test_resolve_model_never_downgrade_stays_opus(router):
    model = router.resolve_model("security-architecture", budget_pct=85.0)
    assert model == OPUS_MODEL


# ---------------------------------------------------------------------------
# 5. resolve_model at 96% budget → haiku for any skill
# ---------------------------------------------------------------------------

def test_resolve_model_emergency_haiku(router):
    for skill in ("systematic-debugging", "security-architecture", "code-review", "tdd"):
        assert router.resolve_model(skill, budget_pct=96.0) == HAIKU_MODEL


# ---------------------------------------------------------------------------
# 6. apply_context_routing under threshold → default model
# ---------------------------------------------------------------------------

def test_context_routing_under_threshold(router):
    model = router.apply_context_routing(token_count=10_000)
    assert model == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# 7. apply_context_routing over threshold → large_context_model
# ---------------------------------------------------------------------------

def test_context_routing_over_threshold(router):
    model = router.apply_context_routing(token_count=60_000)
    # large_context_model in yaml is claude-sonnet-4-6
    assert model == "claude-sonnet-4-6"


def test_context_routing_exactly_at_threshold(router):
    # > threshold, not >=, so exactly 50000 should return default
    assert router.apply_context_routing(50_000) == DEFAULT_MODEL


def test_context_routing_one_over_threshold(router):
    assert router.apply_context_routing(50_001) == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# 8. YAML not found → falls back to defaults without crashing
# ---------------------------------------------------------------------------

def test_fallback_when_config_missing(router_no_config):
    # Must not raise; must return a sensible default
    model = router_no_config.resolve_model("unknown-skill", budget_pct=0.0)
    assert isinstance(model, str)
    assert len(model) > 0
    assert router_no_config._default_model() == DEFAULT_MODEL


def test_fallback_resolve_model_uses_default(router_no_config):
    # No routing_rules → skill not found → default model returned
    assert router_no_config.resolve_model("any-skill") == DEFAULT_MODEL


def test_fallback_context_routing(router_no_config):
    assert router_no_config.apply_context_routing(100) == DEFAULT_MODEL
    assert router_no_config.apply_context_routing(100_000) == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# 9. Existing route_for_plugin still works
# ---------------------------------------------------------------------------

def test_route_for_plugin_monitoring(router):
    plugin = router.route_for_plugin("Track cost and burn rate for this session")
    assert plugin == "monitoring"


def test_route_for_plugin_codereview(router):
    plugin = router.route_for_plugin("Review my Python file auth.py for issues")
    assert plugin == "codereview_bridge"


def test_route_for_plugin_playwright(router):
    plugin = router.route_for_plugin("Test the React component visually")
    assert plugin == "playwright_bridge"


def test_route_for_plugin_none(router):
    plugin = router.route_for_plugin("Summarize this meeting notes")
    assert plugin is None


# ---------------------------------------------------------------------------
# 10. Existing fallback_models still works
# ---------------------------------------------------------------------------

def test_fallback_models_sequence(router):
    models = router.fallback_models(current=OPUS_MODEL)
    assert DEFAULT_MODEL in models
    assert HAIKU_MODEL in models


def test_fallback_excludes_current(router):
    models = router.fallback_models(current=DEFAULT_MODEL)
    assert DEFAULT_MODEL not in models


# ---------------------------------------------------------------------------
# Custom-config fixture extra checks
# ---------------------------------------------------------------------------

def test_custom_config_opus(router_custom):
    assert router_custom.resolve_model("system-design") == OPUS_MODEL


def test_custom_config_haiku(router_custom):
    assert router_custom.resolve_model("ping_session") == HAIKU_MODEL


def test_custom_config_never_downgrade_at_high_budget(router_custom):
    # security-architecture is never_downgrade AND opus
    assert router_custom.resolve_model("security-architecture", budget_pct=85.0) == OPUS_MODEL


def test_custom_config_downgrade_regular_opus(router_custom):
    # system-design is opus but NOT in never_downgrade → downgraded at 85%
    assert router_custom.resolve_model("system-design", budget_pct=85.0) == DEFAULT_MODEL


def test_custom_config_unknown_skill_returns_default(router_custom):
    assert router_custom.resolve_model("totally-unknown-skill") == DEFAULT_MODEL
