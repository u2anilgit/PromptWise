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


@tool(name="update_incident", description="Advance an incident's status along the enforced lifecycle (open->triaged->contained->resolved->closed, linear only, no skipping). Returns an error object (not a raised exception) on an illegal transition.",
         schema={"type": "object", "properties": {
             "incident_id": {"type": "integer"}, "status": {"type": "string"},
             "actor": {"type": "string", "default": ""}},
         "required": ["incident_id", "status"]})
async def _handle_update_incident(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.incidents import IncidentStore
    try:
        inc = IncidentStore().update_status(
            int(arguments.get("incident_id", -1)), arguments.get("status", ""),
            actor=arguments.get("actor", ""))
    except ValueError as e:
        return json.dumps({"error": str(e), "type": "IllegalTransition"})
    return json.dumps(inc.to_dict())


@tool(name="close_incident", description="Close a 'resolved' incident and auto-capture a learning (mistake/correction) into the learning store. Requires the incident to already be in 'resolved' status -- returns an error object otherwise.",
         schema={"type": "object", "properties": {
             "incident_id": {"type": "integer"}, "actor": {"type": "string", "default": ""},
             "mistake": {"type": "string"}, "correction": {"type": "string"},
             "project": {"type": "string", "default": ""}, "tags": {"type": "array", "items": {"type": "string"}, "default": []}},
         "required": ["incident_id", "mistake", "correction"]})
async def _handle_close_incident(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.incidents import IncidentStore
    from promptwise.core.learning_store import LearningStore
    try:
        inc = IncidentStore().update_status(
            int(arguments.get("incident_id", -1)), "closed", actor=arguments.get("actor", ""))
    except ValueError as e:
        return json.dumps({"error": str(e), "type": "IllegalTransition"})
    LearningStore().capture(
        category="incident", mistake=arguments.get("mistake", ""),
        correction=arguments.get("correction", ""), project=arguments.get("project", ""),
        tags=arguments.get("tags", []))
    out = inc.to_dict()
    out["learning_captured"] = True
    return json.dumps(out)
