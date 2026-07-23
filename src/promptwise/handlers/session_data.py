"""handlers.session_data -- session usage/stats MCP tool handlers (moved
verbatim from server.py's "Session Data" section during the handlers/
package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.config import load_config
from promptwise.core.tool_registry import ServerContext, tool


@tool(name="get_session_stats", description="Get session usage statistics",
         schema={"type": "object", "properties": {"since": {"type": "string", "description": "ISO 8601 timestamp filter"}}})
async def _handle_get_session_stats(ctx: ServerContext, arguments: dict) -> str:
    snap = await ctx.memory.snapshot(since=arguments.get("since"))
    pricing_age = getattr(ctx.config, "last_verified", None)
    return json.dumps({**snap, "pricing_last_verified": pricing_age})


@tool(name="clear_history", description="Delete usage history older than N days",
         schema={"type": "object", "properties": {"older_than_days": {"type": "integer", "minimum": 1}}, "required": ["older_than_days"]})
async def _handle_clear_history(ctx: ServerContext, arguments: dict) -> str:
    deleted = await ctx.memory.clear_old(older_than_days=int(arguments.get("older_than_days", 90)))
    return json.dumps({"deleted_count": deleted, "older_than_days": arguments.get("older_than_days", 90)})


@tool(name="export_stats", description="Export usage history as JSON",
         schema={"type": "object", "properties": {"since": {"type": "string"}, "format": {"type": "string", "enum": ["json", "csv"], "default": "json"}}})
async def _handle_export_stats(ctx: ServerContext, arguments: dict) -> str:
    raw = await ctx.memory.export_json(since=arguments.get("since"))
    if arguments.get("format", "json") != "csv":
        return raw
    import csv
    import io
    entries = json.loads(raw)
    buf = io.StringIO()
    fieldnames = ["entry_id", "session_id", "ts", "tool", "summary", "cost_usd", "tags"]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for e in entries:
        writer.writerow({**e, "tags": json.dumps(e["tags"])})
    return buf.getvalue()


@tool(name="reload_config", description="Reload configuration without restarting server",
         schema={"type": "object", "properties": {}})
async def _handle_reload_config(ctx: ServerContext, arguments: dict) -> str:
    ctx.config = load_config()
    return json.dumps({"reloaded": True})
