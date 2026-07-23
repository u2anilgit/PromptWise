"""handlers.memory_session -- memory/session MCP tool handlers (moved
verbatim from server.py's "Memory & Session" section during the
handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool


@tool(name="get_memory_context", description="Retrieve past memory entries for a session",
         schema={"type": "object", "properties": {"session_id": {"type": "string"}, "limit": {"type": "integer", "default": 20}}, "required": ["session_id"]})
async def _handle_get_memory_context(ctx: ServerContext, arguments: dict) -> str:
    entries = await ctx.memory.get_context(session_id=arguments.get("session_id", ""), limit=int(arguments.get("limit", 20)))
    return json.dumps([{"entry_id": e.entry_id, "tool": e.tool, "summary": e.summary, "ts": e.ts} for e in entries])


@tool(name="query_memory", description="Query cross-session episodic and semantic memory",
         schema={"type": "object", "properties": {"query": {"type": "string"}, "scope": {"type": "string", "enum": ["session", "org"], "default": "org"}}, "required": ["query"]})
async def _handle_query_memory(ctx: ServerContext, arguments: dict) -> str:
    facts = await ctx.memory.query_facts(arguments.get("query", ""))
    return json.dumps({"facts": facts})


@tool(name="ping_session", description="Record session activity to reset idle clock",
         schema={"type": "object", "properties": {"session_id": {"type": "string"}}})
async def _handle_ping_session(ctx: ServerContext, arguments: dict) -> str:
    r = await ctx.session_manager.ping(session_id=arguments.get("session_id"))
    return json.dumps(r)


@tool(name="check_session_timeout", description="Check if session has exceeded idle thresholds",
         schema={"type": "object", "properties": {"session_id": {"type": "string"}, "idle_threshold_minutes": {"type": "integer", "default": 30}, "warn_threshold_minutes": {"type": "integer", "default": 20}}, "required": ["session_id"]})
async def _handle_check_session_timeout(ctx: ServerContext, arguments: dict) -> str:
    r = await ctx.session_manager.check_timeout(
        session_id=arguments.get("session_id", ""),
        idle_threshold_minutes=int(arguments.get("idle_threshold_minutes", 30)),
        warn_threshold_minutes=int(arguments.get("warn_threshold_minutes", 20)))
    return json.dumps(r)
