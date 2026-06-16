"""Workflow planner routes tasks to PromptWise-native skill-pack chains."""
from promptwise_v3.core import WorkflowPlanner

P = WorkflowPlanner()


def test_regulated_greenfield_sets_compliance_gate():
    plan = P.plan("Build a HIPAA-compliant patient portal from scratch")
    assert plan.compliance_gate is True
    skills = [s.skill for s in plan.steps]
    assert "security-architecture" in skills
    assert "owasp_scan" in skills


def test_brownfield_routes_to_debug_refactor():
    plan = P.plan("Refactor the legacy billing module")
    assert plan.workflow.startswith("brownfield")
    assert plan.compliance_gate is False
    assert "systematic-debugging" in [s.skill for s in plan.steps]


def test_docs_only_is_spec_chain():
    plan = P.plan("Write a PRD and user stories for a notifications feature")
    assert plan.workflow == "spec"
    assert "prd-generator" in [s.skill for s in plan.steps]


def test_greenfield_default_full_chain():
    plan = P.plan("Build a new dashboard service")
    assert "tdd" in [s.skill for s in plan.steps]
    assert "code-review" in [s.skill for s in plan.steps]


def test_override_flags_respected():
    plan = P.plan("do something", regulated=True, brownfield=False)
    assert plan.compliance_gate is True
