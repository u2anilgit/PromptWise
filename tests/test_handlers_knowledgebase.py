import json

import pytest

from promptwise.handlers.knowledgebase import (
    _handle_kb_lookup, _handle_list_kb_entries,
    _handle_review_kb_candidates, _handle_promote_kb_candidates,
)


@pytest.fixture
def kb_path(tmp_path, monkeypatch):
    path = tmp_path / "kb.json"
    monkeypatch.setattr("promptwise.handlers.knowledgebase._store_path", lambda: path)
    return path


@pytest.mark.asyncio
async def test_lookup_no_entries_returns_none_method(kb_path):
    result = json.loads(await _handle_kb_lookup(None, {"text": "build a cache"}))
    assert result["method"] == "none"
    assert result["best"] is None


@pytest.mark.asyncio
async def test_review_then_promote_roundtrip(kb_path):
    # seed one unreviewed entry directly via the backend the handler uses
    from promptwise.core.knowledgebase import FileBackend, KnowledgeEntry
    FileBackend(store_path=kb_path).save_entry(KnowledgeEntry(
        id="e1", title="cache-aside", tags=["cache-aside"], summary="s",
        source_prompt="speed up reads", artifact_ref="", status="unreviewed",
        created_by="sess", created_at="2026-08-20T00:00:00Z"))

    review = json.loads(await _handle_review_kb_candidates(None, {}))
    assert review["unreviewed"][0]["id"] == "e1"

    promote = json.loads(await _handle_promote_kb_candidates(
        None, {"ids": ["e1"], "action": "trusted", "reviewer": "alice"}))
    assert promote["promoted"] == ["e1"]

    listed = json.loads(await _handle_list_kb_entries(None, {"status": "trusted"}))
    assert listed["entries"][0]["id"] == "e1"
    assert listed["entries"][0]["reviewed_by"] == "alice"


@pytest.mark.asyncio
async def test_promote_requires_reviewer(kb_path):
    result = json.loads(await _handle_promote_kb_candidates(
        None, {"ids": ["e1"], "action": "trusted", "reviewer": ""}))
    assert "error" in result
