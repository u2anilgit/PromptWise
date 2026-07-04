"""Phase 12 — rank_context tool wiring."""
import asyncio
import json

from promptwise import server as srv


class _Ctx:
    pass


def _call(name, arguments):
    return asyncio.run(srv._HANDLERS[name](_Ctx(), arguments))


def test_tool_registered():
    assert "rank_context" in srv._HANDLERS
    assert any(t.name == "rank_context" for t in srv._TOOL_DEFS)


def test_handler_returns_rank_context_shape(tmp_path):
    out = json.loads(_call("rank_context", {
        "query": "payment charge", "token_budget": 2000,
        "repo_root": str(tmp_path),
        "audit_path": str(tmp_path / ".promptwise" / "audit.jsonl"),
    }))
    assert set(out) == {"included", "dropped_count", "assembled_context", "budget"}


def test_handler_accepts_doc_text(tmp_path):
    out = json.loads(_call("rank_context", {
        "query": "payment charge retries", "token_budget": 2000,
        "repo_root": str(tmp_path),
        "audit_path": str(tmp_path / ".promptwise" / "audit.jsonl"),
        "doc_text": "# Payments\npayment charge retries handling\n",
        "sources": ["doc"],
    }))
    assert any(c["source"] == "doc" for c in out["included"])
