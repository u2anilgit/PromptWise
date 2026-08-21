import json

import pytest
import yaml

from promptwise.core.policy import Policy


def test_from_dict_parses_maps_to():
    pol = Policy.from_dict({"maps_to": ["gdpr:art32", "hipaa:164.312(b)"]})
    assert pol.maps_to == ["gdpr:art32", "hipaa:164.312(b)"]


def test_from_dict_maps_to_defaults_to_empty_list():
    pol = Policy.from_dict({})
    assert pol.maps_to == []


def test_evaluate_action_always_carries_control_ids_regardless_of_outcome():
    pol = Policy.from_dict({"maps_to": ["gdpr:art25"], "banned_operations": ["deploy"]})
    allowed_decision = pol.evaluate_action(operation="read")
    blocked_decision = pol.evaluate_action(operation="deploy")
    assert allowed_decision.control_ids == ["gdpr:art25"]
    assert blocked_decision.control_ids == ["gdpr:art25"]
    assert allowed_decision.to_dict()["control_ids"] == ["gdpr:art25"]


def test_merge_tighten_unions_parent_and_child_maps_to(tmp_path):
    parent_path = tmp_path / "parent.yaml"
    parent_path.write_text(yaml.dump({"maps_to": ["gdpr:art32"]}), encoding="utf-8")
    child_path = tmp_path / "child.yaml"
    child_path.write_text(yaml.dump({"extends": str(parent_path), "maps_to": ["hipaa:164.312(b)"]}), encoding="utf-8")

    merged = Policy.from_yaml(child_path)
    assert set(merged.maps_to) == {"gdpr:art32", "hipaa:164.312(b)"}


class _FakeCtx:
    pass


@pytest.mark.asyncio
async def test_check_policy_handler_record_to_audit_false_writes_nothing(tmp_path, monkeypatch):
    from promptwise.core.audit_log import AuditLog
    import promptwise.handlers.agile as agile_handlers

    log = AuditLog(path=tmp_path / "audit.jsonl")
    monkeypatch.setattr("promptwise.handlers.agile._get_audit_log", lambda: log)

    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(yaml.dump({"maps_to": ["gdpr:art32"]}), encoding="utf-8")

    await agile_handlers._handle_check_policy(_FakeCtx(), {
        "policy_path": str(policy_path), "operation": "read"})
    assert log.query() == []


@pytest.mark.asyncio
async def test_check_policy_handler_record_to_audit_true_tags_control_ids(tmp_path, monkeypatch):
    from promptwise.core.audit_log import AuditLog
    import promptwise.handlers.agile as agile_handlers

    log = AuditLog(path=tmp_path / "audit.jsonl")
    monkeypatch.setattr("promptwise.handlers.agile._get_audit_log", lambda: log)

    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(yaml.dump({"maps_to": ["gdpr:art32"], "banned_operations": ["deploy"]}), encoding="utf-8")

    out = await agile_handlers._handle_check_policy(_FakeCtx(), {
        "policy_path": str(policy_path), "operation": "deploy", "actor": "ci-bot",
        "record_to_audit": True})
    result = json.loads(out)
    assert result["allowed"] is False
    assert result["control_ids"] == ["gdpr:art32"]

    records = log.query()
    assert len(records) == 1
    assert records[0]["actor"] == "ci-bot"
    assert "control:gdpr:art32" in records[0]["rules_applied"]
    assert records[0]["gate_decision"] == "FAIL"
    assert records[0]["compliance_decision"] == "policy:advisory"
