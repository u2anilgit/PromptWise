"""handlers.decisions -- ADR / decision-memory MCP tool handlers.

See core/decision_store.py and
docs/superpowers/specs/2026-07-24-adr-decision-memory-design.md.
"""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool


@tool(name="record_decision", description="Record an architectural decision (ADR-style): title, context (the situation/forces), decision (what was chosen), and optional consequences/tags. Pass supersedes=<id> to atomically mark an earlier decision as superseded and link it -- one call, no separate supersede step.",
         schema={"type": "object", "properties": {
             "title": {"type": "string"},
             "context": {"type": "string"},
             "decision": {"type": "string"},
             "consequences": {"type": "string", "default": ""},
             "tags": {"type": "string", "default": "", "description": "comma-joined free-form tags, e.g. 'routing,cost'"},
             "status": {"type": "string", "enum": ["proposed", "accepted", "deprecated"], "default": "accepted"},
             "supersedes": {"type": "integer", "description": "id of an earlier decision this one replaces"},
         }, "required": ["title", "context", "decision"]})
async def _handle_record_decision(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.decision_store import DecisionStore
    store = DecisionStore()
    new_id = store.record(
        arguments.get("title", ""),
        arguments.get("context", ""),
        arguments.get("decision", ""),
        consequences=arguments.get("consequences", ""),
        tags=arguments.get("tags", ""),
        status=arguments.get("status", "accepted"),
        supersedes=arguments.get("supersedes"),
    )
    return json.dumps({"id": new_id, "superseded": arguments.get("supersedes")})


@tool(name="query_decisions", description="Query the ADR/decision-memory log. Pass query for a case-insensitive keyword search across title/context/decision/consequences; otherwise lists decisions optionally filtered by status (proposed/accepted/superseded/deprecated) and/or tag (exact tag match, not substring). Newest first.",
         schema={"type": "object", "properties": {
             "query": {"type": "string", "default": ""},
             "status": {"type": "string", "default": ""},
             "tag": {"type": "string", "default": ""},
             "limit": {"type": "integer", "default": 20},
         }})
async def _handle_query_decisions(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.decision_store import DecisionStore
    store = DecisionStore()
    query = arguments.get("query") or ""
    limit = int(arguments.get("limit", 20))
    if query:
        rows = store.search(query)
    else:
        rows = store.list(status=arguments.get("status") or None, tag=arguments.get("tag") or None)
    return json.dumps({"decisions": rows[:limit]})
