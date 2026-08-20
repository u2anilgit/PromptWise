import json

import pytest

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
