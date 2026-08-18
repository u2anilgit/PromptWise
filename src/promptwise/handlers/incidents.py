"""handlers.incidents -- incident response & forensics MCP tool handlers
(WP3). New category, no pre-split ordering to preserve -- see
core/incidents.py, core/playbooks.py, core/aivss.py (shared with WP2).
"""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool


@tool(name="create_incident", description="Open a new incident (status starts 'open'). Optional metadata dict can link back to a triggering source, e.g. a WP2 anomaly finding.",
         schema={"type": "object", "properties": {
             "title": {"type": "string"}, "description": {"type": "string", "default": ""},
             "severity": {"type": "string", "default": "unknown"},
             "metadata": {"type": "object", "default": {}}},
         "required": ["title"]})
async def _handle_create_incident(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.incidents import IncidentStore
    inc = IncidentStore().create(
        arguments.get("title", ""), description=arguments.get("description", ""),
        severity=arguments.get("severity", "unknown"), metadata=arguments.get("metadata", {}))
    return json.dumps(inc.to_dict())


@tool(name="list_incidents", description="List incidents, optionally filtered by status (open/triaged/contained/resolved/closed).",
         schema={"type": "object", "properties": {"status": {"type": "string"}}})
async def _handle_list_incidents(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.incidents import IncidentStore
    incidents = IncidentStore().list_all(status=arguments.get("status"))
    return json.dumps({"incidents": [i.to_dict() for i in incidents]})
