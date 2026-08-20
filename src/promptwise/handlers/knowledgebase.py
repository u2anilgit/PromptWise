"""handlers.knowledgebase -- MCP tools over core/knowledgebase.py. Mirrors
handlers/security.py's review_corpus_candidates/promote_corpus_candidates
shape: a dry-run review step, then an explicit promote/reject step that
requires a named reviewer."""
from __future__ import annotations

import json
from pathlib import Path

from promptwise.core.tool_registry import ServerContext, tool


def _store_path() -> Path:
    """Overridden in tests via monkeypatch. Reads the shared/team path from
    config/admin.yaml when set (Task 6); falls back to the FileBackend
    default (~/.promptwise/knowledgebase.json) otherwise."""
    try:
        from promptwise.core.admin_config import get_admin_settings
        configured = get_admin_settings().get("knowledgebase", {}).get("store_path")
        if configured:
            return Path(configured)
    except Exception:
        pass
    from promptwise.core.knowledgebase import _DEFAULT_STORE_PATH
    return _DEFAULT_STORE_PATH


def _backend():
    from promptwise.core.knowledgebase import FileBackend
    return FileBackend(store_path=_store_path())


@tool(name="kb_lookup", description="Check the opt-in org knowledgebase for a prior design pattern/architecture/tech-stack decision matching this request, before generating a new one from scratch. Tag match first, embedding similarity fallback. Returns method='none' if nothing matches or the KB is empty.",
      schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]})
async def _handle_kb_lookup(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.knowledgebase import match
    result = match(_backend(), arguments.get("text", ""))
    return json.dumps({
        "method": result.method,
        "score": result.score,
        "best": result.best.to_dict() if result.best else None,
    })


@tool(name="list_kb_entries", description="List knowledgebase entries, optionally filtered by status (unreviewed/trusted/rejected).",
      schema={"type": "object", "properties": {"status": {"type": "string", "enum": ["unreviewed", "trusted", "rejected"]}}})
async def _handle_list_kb_entries(ctx: ServerContext, arguments: dict) -> str:
    entries = _backend().list_entries(status=arguments.get("status") or None)
    return json.dumps({"entries": [e.to_dict() for e in entries]})


@tool(name="review_kb_candidates", description="Dry-run: list unreviewed knowledgebase entries awaiting a human decision. Does not mutate anything. Use before promote_kb_candidates.",
      schema={"type": "object", "properties": {}})
async def _handle_review_kb_candidates(ctx: ServerContext, arguments: dict) -> str:
    entries = _backend().list_entries(status="unreviewed")
    return json.dumps({"unreviewed": [e.to_dict() for e in entries], "count": len(entries)})


@tool(name="promote_kb_candidates", description="Mark knowledgebase entries trusted or rejected. Requires a non-empty reviewer name -- this is a human-review gate, matching promote_corpus_candidates' pattern.",
      schema={"type": "object", "properties": {
          "ids": {"type": "array", "items": {"type": "string"}},
          "action": {"type": "string", "enum": ["trusted", "rejected"]},
          "reviewer": {"type": "string"}},
          "required": ["ids", "action", "reviewer"]})
async def _handle_promote_kb_candidates(ctx: ServerContext, arguments: dict) -> str:
    reviewer = (arguments.get("reviewer") or "").strip()
    if not reviewer:
        return json.dumps({"error": "reviewer is required"})
    backend = _backend()
    promoted = []
    for entry_id in arguments.get("ids", []):
        if backend.update_status(entry_id, arguments.get("action", "trusted"), reviewed_by=reviewer):
            promoted.append(entry_id)
    return json.dumps({"promoted": promoted, "action": arguments.get("action", "trusted")})
