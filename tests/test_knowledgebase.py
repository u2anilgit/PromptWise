from pathlib import Path

from promptwise.core.knowledgebase import KnowledgeEntry, FileBackend


def _entry(**overrides) -> KnowledgeEntry:
    base = dict(
        id="e1", title="cache-aside pattern", tags=["pattern:cache-aside", "stack:python"],
        summary="use cache-aside for read-heavy endpoint", source_prompt="speed up repeated reads",
        artifact_ref="", status="unreviewed", created_by="sess-1", created_at="2026-08-20T00:00:00Z",
        reviewed_by="", reviewed_at="",
    )
    base.update(overrides)
    return KnowledgeEntry(**base)


def test_save_and_get_entry(tmp_path):
    backend = FileBackend(store_path=tmp_path / "kb.json")
    backend.save_entry(_entry())

    got = backend.get_entry("e1")
    assert got is not None
    assert got.title == "cache-aside pattern"
    assert got.status == "unreviewed"


def test_get_missing_entry_returns_none(tmp_path):
    backend = FileBackend(store_path=tmp_path / "kb.json")
    assert backend.get_entry("nope") is None


def test_list_entries_filters_by_status(tmp_path):
    backend = FileBackend(store_path=tmp_path / "kb.json")
    backend.save_entry(_entry(id="e1", status="unreviewed"))
    backend.save_entry(_entry(id="e2", status="trusted"))

    trusted = backend.list_entries(status="trusted")
    assert [e.id for e in trusted] == ["e2"]
    assert len(backend.list_entries()) == 2


def test_update_status_marks_reviewer_and_timestamp(tmp_path):
    backend = FileBackend(store_path=tmp_path / "kb.json")
    backend.save_entry(_entry())

    ok = backend.update_status("e1", "trusted", reviewed_by="alice")

    assert ok is True
    got = backend.get_entry("e1")
    assert got.status == "trusted"
    assert got.reviewed_by == "alice"
    assert got.reviewed_at != ""


def test_update_status_missing_entry_returns_false(tmp_path):
    backend = FileBackend(store_path=tmp_path / "kb.json")
    assert backend.update_status("nope", "trusted", reviewed_by="alice") is False


def test_file_backend_persists_across_instances(tmp_path):
    path = tmp_path / "kb.json"
    FileBackend(store_path=path).save_entry(_entry())

    reloaded = FileBackend(store_path=path)
    assert reloaded.get_entry("e1") is not None
