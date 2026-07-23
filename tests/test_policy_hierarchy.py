"""Task 8 (P1) — policy hierarchy: org -> team -> project inheritance.

Design: a policy YAML file may optionally set ``extends: <path>`` pointing at
its parent (org- or team-level) policy. Merge rule is "child may only
tighten, never loosen":
  * banned_operations / required_gates -- union (a child can add more, never
    remove an org-mandated ban/gate).
  * allowed_model_tiers -- intersection when both set (child narrows the org
    allow-list); a child that doesn't set one inherits the parent's.
  * budget_cap_usd -- the lower (tighter) of parent/child when both set.
No parent configured (no ``extends`` key) -- single-tier behavior is
byte-for-byte the pre-existing behavior; existing single-project users see
no change. This is the same design note called out in the gap-closure plan.
"""
from pathlib import Path

import pytest

from promptwise.core.policy import Policy


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_single_tier_policy_unchanged_when_no_extends(tmp_path):
    p = _write(tmp_path / "project.yaml", "budget_cap_usd: 50.0\nbanned_operations: [deploy_prod]\n")
    pol = Policy.from_yaml(p)
    assert pol.budget_cap_usd == 50.0
    assert pol.banned_operations == ["deploy_prod"]


def test_child_inherits_parent_banned_operations_as_union(tmp_path):
    org = _write(tmp_path / "org.yaml", "banned_operations: [format_disk]\n")
    _write(tmp_path / "project.yaml", f"extends: {org.name}\nbanned_operations: [deploy_prod]\n")
    pol = Policy.from_yaml(tmp_path / "project.yaml")
    assert set(pol.banned_operations) == {"format_disk", "deploy_prod"}


def test_child_narrows_allowed_model_tiers_via_intersection(tmp_path):
    org = _write(tmp_path / "org.yaml", "allowed_model_tiers: [fast, balanced, powerful]\n")
    _write(tmp_path / "project.yaml", f"extends: {org.name}\nallowed_model_tiers: [fast, balanced]\n")
    pol = Policy.from_yaml(tmp_path / "project.yaml")
    assert set(pol.allowed_model_tiers) == {"fast", "balanced"}


def test_child_missing_allowed_model_tiers_inherits_parent_verbatim(tmp_path):
    org = _write(tmp_path / "org.yaml", "allowed_model_tiers: [fast, balanced]\n")
    _write(tmp_path / "project.yaml", f"extends: {org.name}\nbudget_cap_usd: 10.0\n")
    pol = Policy.from_yaml(tmp_path / "project.yaml")
    assert set(pol.allowed_model_tiers) == {"fast", "balanced"}


def test_budget_cap_takes_the_tighter_of_parent_and_child(tmp_path):
    org = _write(tmp_path / "org.yaml", "budget_cap_usd: 100.0\n")
    _write(tmp_path / "project.yaml", f"extends: {org.name}\nbudget_cap_usd: 500.0\n")
    pol = Policy.from_yaml(tmp_path / "project.yaml")
    assert pol.budget_cap_usd == 100.0  # child cannot raise the org cap


def test_required_gates_union_across_three_tiers(tmp_path):
    org = _write(tmp_path / "org.yaml", "required_gates: [compliance]\n")
    team = _write(tmp_path / "team.yaml", f"extends: {org.name}\nrequired_gates: [security]\n")
    _write(tmp_path / "project.yaml", f"extends: {team.name}\nrequired_gates: [quality]\n")
    pol = Policy.from_yaml(tmp_path / "project.yaml")
    assert set(pol.required_gates) == {"compliance", "security", "quality"}


def test_extends_path_resolves_relative_to_the_child_file(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    _write(tmp_path / "org.yaml", "banned_operations: [format_disk]\n")
    _write(sub / "project.yaml", "extends: ../org.yaml\nbanned_operations: [deploy_prod]\n")
    pol = Policy.from_yaml(sub / "project.yaml")
    assert set(pol.banned_operations) == {"format_disk", "deploy_prod"}


def test_cyclic_extends_raises_instead_of_infinite_recursion(tmp_path):
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    _write(a, "extends: b.yaml\n")
    _write(b, "extends: a.yaml\n")
    with pytest.raises(ValueError, match="cycle"):
        Policy.from_yaml(a)
