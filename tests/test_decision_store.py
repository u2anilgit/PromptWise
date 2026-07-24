"""ADR / decision-memory store -- see
docs/superpowers/specs/2026-07-24-adr-decision-memory-design.md.
"""
from promptwise.core.decision_store import DecisionStore


def test_record_creates_accepted_row_by_default(tmp_path):
    store = DecisionStore(tmp_path / "dec.db")
    id_ = store.record("Use sqlite for decision log", "need queryable ADRs",
                        "mirror risk_register.py's pattern", ts="2026-07-24T00:00:00Z")
    row = store.get(id_)
    assert row["title"] == "Use sqlite for decision log"
    assert row["status"] == "accepted"
    assert row["created_at"] == "2026-07-24T00:00:00Z"
    assert row["superseded_by"] is None


def test_record_with_supersedes_marks_old_row_superseded(tmp_path):
    store = DecisionStore(tmp_path / "dec.db")
    old_id = store.record("Use JSON files for decision log", "ctx", "decision v1",
                           ts="2026-01-01T00:00:00Z")
    new_id = store.record("Use sqlite for decision log", "ctx", "decision v2",
                           ts="2026-07-24T00:00:00Z", supersedes=old_id)
    old_row = store.get(old_id)
    assert old_row["status"] == "superseded"
    assert old_row["superseded_by"] == new_id
    new_row = store.get(new_id)
    assert new_row["status"] == "accepted"


def test_get_returns_none_for_unknown_id(tmp_path):
    store = DecisionStore(tmp_path / "dec.db")
    assert store.get(999) is None


def test_list_orders_newest_first(tmp_path):
    store = DecisionStore(tmp_path / "dec.db")
    a = store.record("first", "ctx", "d1", ts="2026-01-01T00:00:00Z")
    b = store.record("second", "ctx", "d2", ts="2026-07-24T00:00:00Z")
    rows = store.list()
    assert [r["id"] for r in rows] == [b, a]


def test_list_filters_by_status(tmp_path):
    store = DecisionStore(tmp_path / "dec.db")
    old_id = store.record("old", "ctx", "d1", ts="2026-01-01T00:00:00Z")
    store.record("new", "ctx", "d2", ts="2026-07-24T00:00:00Z", supersedes=old_id)
    accepted = store.list(status="accepted")
    superseded = store.list(status="superseded")
    assert [r["title"] for r in accepted] == ["new"]
    assert [r["title"] for r in superseded] == ["old"]


def test_list_filters_by_tag_exact_match_not_substring(tmp_path):
    store = DecisionStore(tmp_path / "dec.db")
    store.record("api decision", "ctx", "d1", tags="api,backend", ts="2026-07-24T00:00:00Z")
    store.record("apiary decision", "ctx", "d2", tags="apiary", ts="2026-07-24T00:00:00Z")
    rows = store.list(tag="api")
    assert [r["title"] for r in rows] == ["api decision"]


def test_search_matches_case_insensitively_across_fields(tmp_path):
    store = DecisionStore(tmp_path / "dec.db")
    store.record("Routing strategy", "cost pressure was rising", "switch to cheaper tier",
                  consequences="slightly higher latency", ts="2026-07-24T00:00:00Z")
    store.record("Unrelated", "ctx", "decision", ts="2026-07-24T00:00:00Z")
    rows = store.search("COST PRESSURE")
    assert len(rows) == 1
    assert rows[0]["title"] == "Routing strategy"
    rows2 = store.search("latency")
    assert len(rows2) == 1


def test_search_with_empty_query_returns_nothing(tmp_path):
    store = DecisionStore(tmp_path / "dec.db")
    store.record("x", "ctx", "d", ts="2026-07-24T00:00:00Z")
    assert store.search("") == []
