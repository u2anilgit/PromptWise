from promptwise.security.corpus_store import CorpusStore


def test_append_and_list_history(tmp_path):
    store = CorpusStore(tmp_path / "corpus.db")
    row_id = store.append_history(
        action="promote",
        reviewer="alice",
        candidate_path="corpus/candidates_2026_07.json",
        approved_ids=["c1", "c2"],
        rejected_ids=["c3"],
        before={"precision": 0.9, "recall": 0.8, "f1": 0.847, "accuracy": 0.85},
        after={"precision": 0.92, "recall": 0.85, "f1": 0.884, "accuracy": 0.88},
    )
    assert row_id == 1

    rows = store.list_history()
    assert len(rows) == 1
    row = rows[0]
    assert row["action"] == "promote"
    assert row["reviewer"] == "alice"
    assert row["approved_ids"] == ["c1", "c2"]
    assert row["rejected_ids"] == ["c3"]
    assert row["before"]["f1"] == 0.847
    assert row["after"]["f1"] == 0.884
    assert "created_at" in row


def test_list_history_is_most_recent_first(tmp_path):
    store = CorpusStore(tmp_path / "corpus.db")
    store.append_history("promote", "alice", "a.json", ["c1"], [], {}, {})
    store.append_history("promote", "bob", "b.json", ["c2"], [], {}, {})

    rows = store.list_history()
    assert [r["reviewer"] for r in rows] == ["bob", "alice"]


def test_list_history_respects_limit(tmp_path):
    store = CorpusStore(tmp_path / "corpus.db")
    for i in range(5):
        store.append_history("promote", f"r{i}", "a.json", [], [], {}, {})

    assert len(store.list_history(limit=2)) == 2


def test_append_is_truly_append_only_never_updates(tmp_path):
    store = CorpusStore(tmp_path / "corpus.db")
    store.append_history("promote", "alice", "a.json", ["c1"], [], {}, {})
    store.append_history("promote", "alice", "a.json", ["c1"], [], {}, {})

    assert len(store.list_history(limit=10)) == 2
