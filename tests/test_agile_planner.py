"""Tests for the two-phase agile planner (additive)."""
from __future__ import annotations

from promptwise.core.agile_planner import AgilePlanner


def _planner():
    # config_path=None -> hermetic defaults, independent of repo config/agile.yaml
    return AgilePlanner(config_path=None)


def test_two_phase_shape_and_persona_order():
    plan = _planner().plan("build a new todo app")
    planning = [s.persona for s in plan.planning]
    dev_loop = [s.persona for s in plan.dev_loop]
    assert planning == ["agile-analyst", "agile-pm", "agile-ux", "agile-architect", "agile-po"]
    assert dev_loop == ["agile-sm", "agile-dev", "agile-qa"]


def test_tier_mapping():
    plan = _planner().plan("build a new service")
    assert all(s.model_tier == "opus" for s in plan.planning)
    assert all(s.model_tier == "sonnet" for s in plan.dev_loop)


def test_non_regulated_has_no_compliance_graft():
    plan = _planner().plan("build a simple new prototype")
    assert plan.compliance_gate is False
    assert "security-architecture" not in [s.persona for s in plan.planning]
    assert plan.inject_tools == []


def test_regulated_grafts_security_and_tools():
    plan = _planner().plan("build a payments reconciliation service, FINRA relevant")
    assert plan.compliance_gate is True
    personas = [s.persona for s in plan.planning]
    # security-architecture injected right after the architect persona
    assert "security-architecture" in personas
    assert personas.index("security-architecture") == personas.index("agile-architect") + 1
    assert plan.inject_tools == ["owasp_scan", "get_sbom"]


def test_workflow_label_and_serialization():
    plan = _planner().plan("refactor the legacy billing module")
    d = plan.to_dict()
    assert d["workflow"].startswith("agile:")
    assert "planning" in d and "dev_loop" in d
    assert d["signals"]["brownfield"] is True
