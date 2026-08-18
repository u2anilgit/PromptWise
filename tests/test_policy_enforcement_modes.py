"""WP1 1a -- enforcement mode on Policy/PolicyDecision."""
import pytest

from promptwise.core.policy import Policy, PolicyDecision


def test_default_enforcement_is_advisory():
    pol = Policy.from_dict({"banned_operations": ["force_push"]})
    assert pol.enforcement == "advisory"


def test_advisory_default_is_byte_identical_to_pre_wp1_behavior():
    # No enforcement key at all -- the exact shape every existing
    # config/policy.yaml in the wild has today.
    pol = Policy.from_dict({"banned_operations": ["force_push"]})
    dec = pol.evaluate_action(operation="force_push")
    assert dec.allowed is False
    assert dec.violations == ["operation 'force_push' is banned by policy"]
    assert dec.enforcement == "advisory"


def test_explicit_enforcement_modes_parsed():
    for mode in ("advisory", "escalate", "block"):
        pol = Policy.from_dict({"enforcement": mode})
        assert pol.enforcement == mode


def test_unknown_enforcement_mode_rejected():
    with pytest.raises(ValueError, match="enforcement"):
        Policy.from_dict({"enforcement": "yolo"})


def test_evaluate_action_carries_enforcement_onto_decision():
    pol = Policy.from_dict({"enforcement": "block", "banned_operations": ["force_push"]})
    dec = pol.evaluate_action(operation="force_push")
    assert dec.enforcement == "block"
    assert dec.allowed is False


def test_decision_to_dict_includes_enforcement():
    dec = PolicyDecision(allowed=True, enforcement="escalate")
    assert dec.to_dict()["enforcement"] == "escalate"


def test_merge_tighten_takes_stricter_enforcement():
    from promptwise.core.policy import _merge_tighten
    parent = Policy.from_dict({"enforcement": "advisory"})
    child = Policy.from_dict({"enforcement": "block"})
    merged = _merge_tighten(parent, child)
    assert merged.enforcement == "block"
    # and the reverse -- child may not loosen a stricter parent
    parent2 = Policy.from_dict({"enforcement": "block"})
    child2 = Policy.from_dict({"enforcement": "advisory"})
    merged2 = _merge_tighten(parent2, child2)
    assert merged2.enforcement == "block"
