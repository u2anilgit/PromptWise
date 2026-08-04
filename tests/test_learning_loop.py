"""Phase 2 — continuous learning loop: capture, FTS/LIKE retrieval, insights."""
import asyncio
import json
import typing

from promptwise.core.learning_store import LearningStore, _tokenize
from promptwise.core.learning_replay import replay
from promptwise.core.insights import compute_insights


def _store(tmp_path):
    return LearningStore(tmp_path / "learning.db")


def test_capture_and_count(tmp_path):
    s = _store(tmp_path)
    rec = s.capture("style", "used tabs", "use 4 spaces", project="acme", tags=["py"])
    assert rec.id >= 1 and rec.category == "style"
    assert s.count() == 1


def test_search_returns_relevant(tmp_path):
    s = _store(tmp_path)
    s.capture("security", "hardcoded api key in source", "load from env var")
    s.capture("style", "long functions", "extract helpers")
    s.capture("api-misuse", "called requests without timeout", "always pass timeout=")
    hits = s.search("api key leaked in code", k=3)
    assert hits, "expected at least one match"
    assert hits[0].category in ("security", "api-misuse")


def test_search_empty_query_returns_recent(tmp_path):
    s = _store(tmp_path)
    s.capture("a", "m1", "c1")
    s.capture("b", "m2", "c2")
    hits = s.search("", k=5)
    assert len(hits) == 2


def test_project_filter(tmp_path):
    s = _store(tmp_path)
    s.capture("style", "tabs", "spaces", project="proj-a")
    s.capture("style", "tabs", "spaces", project="proj-b")
    hits = s.search("tabs", k=5, project="proj-a")
    assert hits and all(h.project == "proj-a" for h in hits)


def test_like_fallback_when_fts_disabled(tmp_path):
    s = _store(tmp_path)
    s.fts_enabled = False  # force the fallback path
    s.capture("security", "secret in repo", "use a vault")
    hits = s._search_like("secret repo", k=5, project=None)
    assert hits and hits[0].category == "security"


def test_replay_builds_reminder(tmp_path):
    db = tmp_path / "learning.db"
    s = LearningStore(db)
    s.capture("security", "committed a token", "rotate and use env", project="x")
    out = replay("about to commit credentials", k=3, db_path=db)
    assert out["matched"] >= 1
    assert "->" in out["reminder"]
    assert out["learnings"][0]["correction"]


def test_insights_trends(tmp_path):
    db = tmp_path / "learning.db"
    s = LearningStore(db)
    s.capture("security", "m", "c")
    s.capture("security", "m2", "c2")
    s.capture("style", "m3", "c3")
    ins = compute_insights(db)
    assert ins["total_learnings"] == 3
    assert ins["by_category"]["security"] == 2
    assert ins["top_category"] == "security"


def test_tokenize_drops_punctuation_and_singletons():
    assert _tokenize("API_key: a, the-quick!!") == ["api_key", "the", "quick"]


# ── fact supersession (Phase 19 / candidate D1) ────────────────────────────────
def test_supersede_marks_prior_learning_superseded(tmp_path):
    s = _store(tmp_path)
    old = s.capture("style", "use tabs", "tabs are fine", project="acme")
    new = s.capture("style", "use tabs", "actually use 4 spaces", project="acme",
                     supersedes=old.id)
    old_row = [l for l in s.all() if l.id == old.id][0]
    assert old_row.status == "superseded"
    assert old_row.superseded_by == new.id


def test_search_excludes_superseded_by_default(tmp_path):
    s = _store(tmp_path)
    old = s.capture("style", "tabs question", "tabs are fine")
    s.capture("style", "tabs question", "actually use 4 spaces", supersedes=old.id)
    hits = s.search("tabs question", k=5)
    assert all(h.id != old.id for h in hits)
    assert any(h.status == "active" for h in hits)


def test_recent_excludes_superseded_by_default(tmp_path):
    s = _store(tmp_path)
    old = s.capture("a", "m1", "c1")
    s.capture("a", "m1", "c1-fixed", supersedes=old.id)
    hits = s.recent(k=5)
    assert all(h.id != old.id for h in hits)


def test_include_superseded_true_returns_full_history(tmp_path):
    s = _store(tmp_path)
    old = s.capture("a", "m1", "c1")
    s.capture("a", "m1", "c1-fixed", supersedes=old.id)
    hits = s.recent(k=5, include_superseded=True)
    assert any(h.id == old.id for h in hits)


def test_like_fallback_excludes_superseded(tmp_path):
    s = _store(tmp_path)
    s.fts_enabled = False
    old = s.capture("security", "secret in repo", "use a vault")
    s.capture("security", "secret in repo", "use a vault, rotated", supersedes=old.id)
    hits = s._search_like("secret repo", k=5, project=None)
    assert all(h.id != old.id for h in hits)


def test_all_returns_full_history_including_superseded(tmp_path):
    s = _store(tmp_path)
    old = s.capture("a", "m1", "c1")
    s.capture("a", "m1", "c1-fixed", supersedes=old.id)
    assert len(s.all()) == 2  # insights.py's trend analysis wants full history


def test_existing_db_without_supersession_columns_migrates_cleanly(tmp_path):
    import sqlite3
    db = tmp_path / "old_learning.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        """CREATE TABLE learnings (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               ts TEXT NOT NULL, category TEXT NOT NULL DEFAULT '',
               mistake TEXT NOT NULL DEFAULT '', correction TEXT NOT NULL DEFAULT '',
               project TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '[]'
           )"""
    )
    conn.execute(
        "INSERT INTO learnings (ts, category, mistake, correction) "
        "VALUES ('2026-01-01T00:00:00Z', 'a', 'm', 'c')")
    conn.commit()
    conn.close()
    s = LearningStore(db)  # triggers the ALTER TABLE migration
    rows = s.all()
    assert len(rows) == 1
    assert rows[0].status == "active"
    assert rows[0].superseded_by is None
    # and the migrated store still supports superseding the pre-existing row
    s.capture("a", "m", "c-fixed", supersedes=rows[0].id)
    assert [l for l in s.all() if l.id == rows[0].id][0].status == "superseded"


def test_capture_learning_tool_supports_supersedes(tmp_path, monkeypatch):
    import promptwise.core.learning_store as ls
    db = tmp_path / "learning.db"
    monkeypatch.setattr(ls, "default_db_path", lambda: db)
    import promptwise.server as srv

    ctx = typing.cast(srv.ServerContext, None)
    first = json.loads(asyncio.run(srv.call_tool(ctx, "capture_learning", {
        "category": "style", "mistake": "tabs", "correction": "tabs are fine"})))
    second = json.loads(asyncio.run(srv.call_tool(ctx, "capture_learning", {
        "category": "style", "mistake": "tabs", "correction": "use 4 spaces",
        "supersedes": first["captured"]["id"]})))
    assert second["captured"]["id"] != first["captured"]["id"]
    store = ls.LearningStore(db)
    old_row = [l for l in store.all() if l.id == first["captured"]["id"]][0]
    assert old_row.status == "superseded"


def test_empty_store_insights(tmp_path):
    ins = compute_insights(tmp_path / "learning.db")
    assert ins["total_learnings"] == 0
    assert ins["top_category"] is None


# ── server dispatch (monkeypatch the home db so tests stay hermetic) ──────────
def test_server_dispatch_capture_replay_insights(tmp_path, monkeypatch):
    import promptwise.core.learning_store as ls
    db = tmp_path / "learning.db"
    monkeypatch.setattr(ls, "default_db_path", lambda: db)
    import promptwise.server as srv

    # None is a valid stand-in: none of these handlers read ctx. Cast documents
    # the intentional gap instead of building a real 23-field ServerContext.
    ctx = typing.cast(srv.ServerContext, None)

    cap = json.loads(asyncio.run(srv.call_tool(ctx, "capture_learning", {
        "category": "security", "mistake": "logged a password",
        "correction": "redact secrets before logging", "project": "acme"})))
    assert cap["captured"]["id"] >= 1

    rep = json.loads(asyncio.run(srv.call_tool(ctx, "replay_learnings",
                                               {"task": "add logging to auth", "k": 3})))
    assert rep["matched"] >= 1

    ins = json.loads(asyncio.run(srv.call_tool(ctx, "learning_insights", {})))
    assert ins["total_learnings"] >= 1
