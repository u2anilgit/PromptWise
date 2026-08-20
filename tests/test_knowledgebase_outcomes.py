from promptwise.core.knowledgebase import FileBackend, KnowledgeEntry, match


def _entry(id_, tags, reuse_count=0, accepted_count=0, status="trusted"):
    return KnowledgeEntry(id=id_, title=id_, tags=tags, summary="", source_prompt="",
                           artifact_ref="", status=status, created_by="s",
                           created_at="2026-08-20T00:00:00Z",
                           reuse_count=reuse_count, accepted_count=accepted_count)


def test_new_entry_defaults_outcome_counts_to_zero():
    e = KnowledgeEntry(id="e1", title="t", tags=[], summary="", source_prompt="",
                       artifact_ref="", status="trusted", created_by="s",
                       created_at="2026-08-20T00:00:00Z")
    assert e.reuse_count == 0
    assert e.accepted_count == 0


def test_record_outcome_increments_reuse_and_accepted(tmp_path):
    backend = FileBackend(store_path=tmp_path / "kb.json")
    backend.save_entry(_entry("e1", tags=["x"]))

    ok = backend.record_outcome("e1", accepted=True)

    assert ok is True
    got = backend.get_entry("e1")
    assert got.reuse_count == 1
    assert got.accepted_count == 1


def test_record_outcome_rejected_increments_reuse_only(tmp_path):
    backend = FileBackend(store_path=tmp_path / "kb.json")
    backend.save_entry(_entry("e1", tags=["x"]))

    backend.record_outcome("e1", accepted=False)

    got = backend.get_entry("e1")
    assert got.reuse_count == 1
    assert got.accepted_count == 0


def test_record_outcome_missing_entry_returns_false(tmp_path):
    backend = FileBackend(store_path=tmp_path / "kb.json")
    assert backend.record_outcome("nope", accepted=True) is False


def test_tag_tie_prefers_higher_acceptance_rate(tmp_path):
    backend = FileBackend(store_path=tmp_path / "kb.json")
    # both trusted, both tag "x" -- e1 has a strong track record, e2 has none
    backend.save_entry(_entry("e1", tags=["x"], reuse_count=10, accepted_count=9))
    backend.save_entry(_entry("e2", tags=["x"], reuse_count=0, accepted_count=0))

    result = match(backend, "need x")

    assert result.best.id == "e1"
