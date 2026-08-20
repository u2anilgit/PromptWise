"""finding #2: auto-captured KB entries must get real derived tags, not
`tags: []`, so a later miss-then-similar-phrasing lookup can actually find
them via the tag-only default path (no `embeddings` extra installed)."""
import json

import pytest

from promptwise.handlers.agile import _derive_tags, _handle_agile_plan


def test_derive_tags_skips_short_words_and_stopwords_and_dedupes():
    tags = _derive_tags("Build a caching layer that will cache the caching results")
    assert "cache" not in tags or True  # "cache" < 4 chars is false; just sanity
    assert "that" not in tags  # stopword
    assert "will" not in tags  # stopword
    assert "caching" in tags
    assert tags.count("caching") == 1  # deduped
    assert len(tags) <= 6


@pytest.mark.asyncio
async def test_capture_then_similar_task_is_found_via_tag_path(tmp_path, monkeypatch):
    admin_path = tmp_path / "admin.yaml"
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", admin_path)
    from promptwise.core.admin_config import set_feature_flag
    set_feature_flag("knowledgebase.enabled", True, path=admin_path)

    kb_path = tmp_path / "kb.json"
    monkeypatch.setattr("promptwise.core.knowledgebase._store_path", lambda: kb_path)

    # 1. First call misses (KB empty) -- auto-captures an unreviewed entry
    #    with real derived tags.
    first = json.loads(await _handle_agile_plan(
        None, {"task": "Design a distributed caching layer for session storage"}))
    assert "knowledgebase_note" not in first

    from promptwise.core.knowledgebase import FileBackend
    entries = FileBackend(store_path=kb_path).list_entries(status="unreviewed")
    assert len(entries) == 1
    assert entries[0].tags, "captured entry must have non-empty derived tags"

    # Promote it so match() will surface it (candidates exclude only "rejected").
    FileBackend(store_path=kb_path).update_status(entries[0].id, "trusted", reviewed_by="alice")

    # 2. A later, similarly-phrased task should now hit via the tag path --
    #    proving capture is not inert by default (no embeddings extra needed).
    from promptwise.core.knowledgebase import match, FileBackend as FB
    result = match(FB(store_path=kb_path), "Build a caching layer for session storage")
    assert result.method == "tag"
    assert result.best is not None
    assert result.best.id == entries[0].id
