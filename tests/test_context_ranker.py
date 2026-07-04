"""Phase 12 — rank_context: fuse audit/learnings/doc candidates onto one
ranked list, prune to a token budget (word-count proxy, matching
Optimizer.optimize()'s existing convention)."""
import json

from promptwise.core.context_ranker import rank_context


def _write_audit(tmp_path, tasks):
    d = tmp_path / ".promptwise"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "audit.jsonl").open("w", encoding="utf-8") as fh:
        for i, t in enumerate(tasks):
            fh.write(json.dumps({"index": i, "timestamp": "2026-01-01T00:00:00Z",
                                 "task": t, "agent": "claude-code", "files_touched": []}) + "\n")


def test_ranks_audit_candidates_by_score(tmp_path):
    _write_audit(tmp_path, ["Refactor payment charge logic", "Write docs for login"])
    out = rank_context("payment charge", token_budget=2000, repo_root=tmp_path,
                       audit_path=tmp_path / ".promptwise" / "audit.jsonl",
                       learning_db=str(tmp_path / "ldb.db"))
    assert out["included"]
    assert any("payment" in c["text"] for c in out["included"])
    assert all(c["source"] == "audit" for c in out["included"])


def test_includes_doc_shard_candidates_when_doc_text_given(tmp_path):
    doc = "# Payments\nHandle payment charge retries.\n\n# Login\nUnrelated login flow.\n"
    out = rank_context("payment charge retries", token_budget=2000, repo_root=tmp_path,
                       audit_path=tmp_path / ".promptwise" / "audit.jsonl",
                       learning_db=str(tmp_path / "ldb.db"),
                       doc_text=doc)
    doc_hits = [c for c in out["included"] if c["source"] == "doc"]
    assert doc_hits
    assert any("charge retries" in c["text"] for c in doc_hits)


def test_sources_filter_excludes_doc_when_not_requested(tmp_path):
    doc = "# Payments\nHandle payment charge retries.\n"
    out = rank_context("payment charge retries", token_budget=2000, repo_root=tmp_path,
                       audit_path=tmp_path / ".promptwise" / "audit.jsonl",
                       learning_db=str(tmp_path / "ldb.db"),
                       doc_text=doc, sources=("audit", "learnings"))
    assert not any(c["source"] == "doc" for c in out["included"])


def test_budget_prunes_lowest_scored_candidates_first(tmp_path):
    doc = ("# A\n" + ("payment charge retries logic detail extra words here padding " * 20) + "\n"
          "# B\nunrelated filler section with no matching terms at all here padding\n")
    out = rank_context("payment charge retries", token_budget=15, repo_root=tmp_path,
                       audit_path=tmp_path / ".promptwise" / "audit.jsonl",
                       learning_db=str(tmp_path / "ldb.db"),
                       doc_text=doc, sources=("doc",))
    assert out["budget"]["total"] == 15
    assert out["budget"]["used"] <= 15
    assert out["dropped_count"] >= 1
    included_texts = " ".join(c["text"] for c in out["included"])
    assert "unrelated filler" not in included_texts


def test_zero_budget_drops_everything(tmp_path):
    doc = "# A\npayment charge retries\n"
    out = rank_context("payment charge retries", token_budget=0, repo_root=tmp_path,
                       audit_path=tmp_path / ".promptwise" / "audit.jsonl",
                       learning_db=str(tmp_path / "ldb.db"),
                       doc_text=doc, sources=("doc",))
    assert out["included"] == []
    assert out["dropped_count"] == 1
    assert out["assembled_context"] == ""


def test_empty_query_and_empty_corpus_returns_cleanly(tmp_path):
    out = rank_context("", token_budget=2000, repo_root=tmp_path,
                       audit_path=tmp_path / ".promptwise" / "audit.jsonl",
                       learning_db=str(tmp_path / "ldb.db"))
    assert out == {"included": [], "dropped_count": 0, "assembled_context": "",
                   "budget": {"total": 2000, "used": 0}}


def test_broken_doc_path_fails_soft(tmp_path):
    _write_audit(tmp_path, ["Refactor payment charge logic"])
    out = rank_context("payment charge", token_budget=2000, repo_root=tmp_path,
                       audit_path=tmp_path / ".promptwise" / "audit.jsonl",
                       learning_db=str(tmp_path / "ldb.db"),
                       doc_path=str(tmp_path / "does-not-exist.md"))
    assert not any(c["source"] == "doc" for c in out["included"])
    assert any(c["source"] == "audit" for c in out["included"])


def test_assembled_context_joins_included_in_ranked_order(tmp_path):
    doc = "# A\npayment charge retries alpha\n\n# B\npayment charge retries beta\n"
    out = rank_context("payment charge retries", token_budget=2000, repo_root=tmp_path,
                       audit_path=tmp_path / ".promptwise" / "audit.jsonl",
                       learning_db=str(tmp_path / "ldb.db"),
                       doc_text=doc, sources=("doc",))
    assert out["assembled_context"] == "\n\n".join(c["text"] for c in out["included"])
