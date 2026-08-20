from promptwise.core.knowledgebase import kb_precheck, FileBackend, KnowledgeEntry


def test_miss_with_no_capture_arg_saves_nothing(tmp_path, monkeypatch):
    admin_path = tmp_path / "admin.yaml"
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", admin_path)
    from promptwise.core.admin_config import set_feature_flag
    set_feature_flag("knowledgebase.enabled", True, path=admin_path)

    kb_path = tmp_path / "kb.json"
    monkeypatch.setattr("promptwise.core.knowledgebase._store_path", lambda: kb_path)

    note = kb_precheck("brand new request shape")
    assert note is None
    assert FileBackend(store_path=kb_path).list_entries() == []


def test_miss_with_capture_saves_unreviewed_entry(tmp_path, monkeypatch):
    admin_path = tmp_path / "admin.yaml"
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", admin_path)
    from promptwise.core.admin_config import set_feature_flag
    set_feature_flag("knowledgebase.enabled", True, path=admin_path)

    kb_path = tmp_path / "kb.json"
    monkeypatch.setattr("promptwise.core.knowledgebase._store_path", lambda: kb_path)

    note = kb_precheck("brand new request shape", created_by="sess-1",
                        capture={"title": "new pattern", "tags": ["new-tag"], "summary": "s"})

    assert note is None  # nothing to surface on a miss
    entries = FileBackend(store_path=kb_path).list_entries(status="unreviewed")
    assert len(entries) == 1
    assert entries[0].title == "new pattern"
    assert entries[0].created_by == "sess-1"


def test_disabled_kb_never_captures(tmp_path, monkeypatch):
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", tmp_path / "admin.yaml")
    kb_path = tmp_path / "kb.json"
    monkeypatch.setattr("promptwise.core.knowledgebase._store_path", lambda: kb_path)

    kb_precheck("anything", capture={"title": "t", "tags": [], "summary": "s"})

    assert FileBackend(store_path=kb_path).list_entries() == []


def test_project_scoped_flag_activates_kb_for_that_project(tmp_path, monkeypatch):
    """finding #3: kb_precheck must honor project_features[project] first,
    falling back to the global flag only when no project override exists."""
    admin_path = tmp_path / "admin.yaml"
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", admin_path)
    from promptwise.core.admin_config import set_feature_flag
    # Global flag stays OFF; only the project-scoped flag is turned on.
    set_feature_flag("knowledgebase.enabled", True, project="team-a", path=admin_path)

    kb_path = tmp_path / "kb.json"
    monkeypatch.setattr("promptwise.core.knowledgebase._store_path", lambda: kb_path)
    FileBackend(store_path=kb_path).save_entry(KnowledgeEntry(
        id="e1", title="cache-aside pattern", tags=["caching"], summary="s",
        source_prompt="build a caching layer", artifact_ref="", status="trusted",
        created_by="sess", created_at="2026-08-20T00:00:00Z"))

    # project passed and matches the project-scoped ON flag -> active.
    note = kb_precheck("build a caching layer", project="team-a")
    assert note is not None
    assert note["title"] == "cache-aside pattern"

    # project not passed -> falls back to the (currently off) global flag -> inactive.
    note_no_project = kb_precheck("build a caching layer")
    assert note_no_project is None

    # a different, unconfigured project also falls back to the global flag -> inactive.
    note_other_project = kb_precheck("build a caching layer", project="team-b")
    assert note_other_project is None
