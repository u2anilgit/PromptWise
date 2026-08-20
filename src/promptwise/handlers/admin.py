"""handlers.admin -- MCP tools over core/admin_config.py. Same functions
the dashboard Admin tab calls (Task 9) -- one code path, two entry
points."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool


@tool(name="set_feature_flag", description="Turn an opt-in PromptWise feature on/off, globally or for one project (e.g. name='knowledgebase.enabled'). Project-scoped flags override the global default only when that project_id is passed by the caller checking the flag.",
      schema={"type": "object", "properties": {
          "name": {"type": "string"}, "enabled": {"type": "boolean"},
          "project": {"type": "string"}},
          "required": ["name", "enabled"]})
async def _handle_set_feature_flag(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.admin_config import set_feature_flag
    set_feature_flag(arguments.get("name", ""), bool(arguments.get("enabled", False)),
                      project=arguments.get("project") or None)
    return json.dumps({"status": "ok", "name": arguments.get("name"),
                       "enabled": arguments.get("enabled"), "project": arguments.get("project")})


@tool(name="get_admin_settings", description="Read the full admin config: feature flags (global + per-project), knowledgebase settings. Budget limits live in BudgetGuardian/set_budget_limit, not here.",
      schema={"type": "object", "properties": {}})
async def _handle_get_admin_settings(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.admin_config import get_admin_settings
    return json.dumps(get_admin_settings())
