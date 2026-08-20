from promptwise.core.knowledgebase import kb_precheck, FileBackend


def test_miss_with_no_capture_arg_saves_nothing(tmp_path, monkeypatch):
    admin_path = tmp_path / "admin.yaml"
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", admin_path)
    from promptwise.core.admin_config import set_feature_flag
    set_feature_flag("knowledgebase.enabled", True, path=admin_path)

    kb_path = tmp_path / "kb.json"
    monkeypatch.setattr("promptwise.handlers.knowledgebase._store_path", lambda: kb_path)

    note = kb_precheck("brand new request shape")
    assert note is None
    assert FileBackend(store_path=kb_path).list_entries() == []


def test_miss_with_capture_saves_unreviewed_entry(tmp_path, monkeypatch):
    admin_path = tmp_path / "admin.yaml"
    monkeypatch.setattr("promptwise.core.admin_config._DEFAULT_PATH", admin_path)
    from promptwise.core.admin_config import set_feature_flag
    set_feature_flag("knowledgebase.enabled", True, path=admin_path)

    kb_path = tmp_path / "kb.json"
    monkeypatch.setattr("promptwise.handlers.knowledgebase._store_path", lambda: kb_path)

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
    monkeypatch.setattr("promptwise.handlers.knowledgebase._store_path", lambda: kb_path)

    kb_precheck("anything", capture={"title": "t", "tags": [], "summary": "s"})

    assert FileBackend(store_path=kb_path).list_entries() == []
