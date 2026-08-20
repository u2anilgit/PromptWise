import json

import pytest

from promptwise.core.audit_log import AuditLog
from promptwise.handlers.admin import _handle_set_feature_flag, _handle_get_admin_settings


@pytest.mark.asyncio
async def test_set_and_get_feature_flag(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", tmp_path / "admin.yaml")

    set_result = json.loads(await _handle_set_feature_flag(
        None, {"name": "knowledgebase.enabled", "enabled": True}))
    assert set_result["status"] == "ok"

    settings = json.loads(await _handle_get_admin_settings(None, {}))
    assert settings["features"]["knowledgebase.enabled"] is True


@pytest.mark.asyncio
async def test_set_feature_flag_project_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", tmp_path / "admin.yaml")

    await _handle_set_feature_flag(None, {"name": "knowledgebase.enabled", "enabled": True, "project": "team-a"})

    settings = json.loads(await _handle_get_admin_settings(None, {}))
    assert settings["project_features"]["team-a"]["knowledgebase.enabled"] is True


@pytest.mark.asyncio
async def test_set_feature_flag_is_audited(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", tmp_path / "admin.yaml")
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr("promptwise.handlers.admin._get_audit_log", lambda: AuditLog(audit_path))

    await _handle_set_feature_flag(None, {"name": "knowledgebase.enabled", "enabled": True})

    records = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(records) == 1
    rec = json.loads(records[0])
    assert rec["task"] == "set_feature_flag:knowledgebase.enabled"
    assert rec["gate_decision"] == "enabled"
