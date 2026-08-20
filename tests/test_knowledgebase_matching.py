from promptwise.core.knowledgebase import FileBackend, KnowledgeEntry, match


def _entry(id_, tags, summary="", source_prompt="", status="trusted"):
    return KnowledgeEntry(id=id_, title=id_, tags=tags, summary=summary,
                           source_prompt=source_prompt, artifact_ref="", status=status,
                           created_by="s", created_at="2026-08-20T00:00:00Z")


def test_no_entries_returns_none_method(tmp_path):
    backend = FileBackend(store_path=tmp_path / "kb.json")
    result = match(backend, "build a caching layer")
    assert result.best is None
    assert result.method == "none"


def test_tag_overlap_finds_match(tmp_path):
    backend = FileBackend(store_path=tmp_path / "kb.json")
    backend.save_entry(_entry("e1", tags=["cache-aside", "python"], source_prompt="speed up reads"))

    result = match(backend, "need a cache-aside pattern in python")

    assert result.best is not None
    assert result.best.id == "e1"
    assert result.method == "tag"


def test_rejected_entries_never_surface(tmp_path):
    backend = FileBackend(store_path=tmp_path / "kb.json")
    backend.save_entry(_entry("e1", tags=["cache-aside"], status="rejected"))

    result = match(backend, "need a cache-aside pattern")

    assert result.best is None


def test_embedding_fallback_used_when_no_tag_hit(tmp_path, monkeypatch):
    backend = FileBackend(store_path=tmp_path / "kb.json")
    backend.save_entry(_entry("e1", tags=["unrelated-tag"], source_prompt="speed up repeated database reads"))

    from promptwise.core import knowledgebase as kb_mod

    class _FakeProvider:
        def embed(self, text):
            # deterministic fake: identical vector for both calls -> similarity 1.0
            return [1.0, 0.0]

    monkeypatch.setattr(kb_mod, "_get_embedding_provider", lambda: _FakeProvider())

    result = match(backend, "reduce database read latency")

    assert result.best is not None
    assert result.best.id == "e1"
    assert result.method == "embedding"


def test_no_embeddings_extra_falls_back_to_none(tmp_path, monkeypatch):
    backend = FileBackend(store_path=tmp_path / "kb.json")
    backend.save_entry(_entry("e1", tags=["unrelated-tag"], source_prompt="speed up repeated database reads"))

    from promptwise.core import knowledgebase as kb_mod
    monkeypatch.setattr(kb_mod, "_get_embedding_provider", lambda: None)

    result = match(backend, "reduce database read latency")

    assert result.best is None
    assert result.method == "none"
