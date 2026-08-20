import json

import pytest

from promptwise.handlers.agile import _handle_agile_plan


@pytest.mark.asyncio
async def test_kb_disabled_by_default_no_note(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", tmp_path / "admin.yaml")
    result = json.loads(await _handle_agile_plan(None, {"task": "build a caching layer"}))
    assert "knowledgebase_note" not in result


@pytest.mark.asyncio
async def test_kb_enabled_with_trusted_match_adds_note(tmp_path, monkeypatch):
    admin_path = tmp_path / "admin.yaml"
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", admin_path)
    from promptwise.core.admin_config import set_feature_flag
    set_feature_flag("knowledgebase.enabled", True, path=admin_path)

    kb_path = tmp_path / "kb.json"
    from promptwise.core.knowledgebase import FileBackend, KnowledgeEntry
    FileBackend(store_path=kb_path).save_entry(KnowledgeEntry(
        id="e1", title="cache-aside pattern", tags=["caching layer"], summary="s",
        source_prompt="build a caching layer", artifact_ref="", status="trusted",
        created_by="sess", created_at="2026-08-20T00:00:00Z"))
    monkeypatch.setattr("promptwise.handlers.knowledgebase._store_path", lambda: kb_path)

    result = json.loads(await _handle_agile_plan(None, {"task": "build a caching layer"}))

    assert "knowledgebase_note" in result
    assert result["knowledgebase_note"]["title"] == "cache-aside pattern"
