"""handlers.admin -- MCP tools over core/admin_config.py. Same functions
the dashboard Admin tab calls (Task 9) -- one code path, two entry
points."""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool, _get_audit_log


@tool(name="set_feature_flag", description="Turn an opt-in PromptWise feature on/off, globally or for one project (e.g. name='knowledgebase.enabled'). Project-scoped flags override the global default only when that project_id is passed by the caller checking the flag.",
      schema={"type": "object", "properties": {
          "name": {"type": "string"}, "enabled": {"type": "boolean"},
          "project": {"type": "string"}},
          "required": ["name", "enabled"]})
async def _handle_set_feature_flag(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.admin_config import set_feature_flag
    name = arguments.get("name", "")
    enabled = bool(arguments.get("enabled", False))
    project = arguments.get("project") or None
    set_feature_flag(name, enabled, project=project)
    # Admin config changes are governance-relevant (they flip runtime
    # behavior, e.g. knowledgebase.enabled) -- audit like governor actions,
    # not silent like the corpus-promote precedent. Fail-open: never let a
    # sink issue block the actual flag write, which already succeeded above.
    try:
        _get_audit_log().append(
            f"set_feature_flag:{name}", actor="admin",
            gate_decision="enabled" if enabled else "disabled",
            files_touched=[f"admin_config:{project}" if project else "admin_config:global"])
    except Exception:
        pass
    return json.dumps({"status": "ok", "name": name,
                       "enabled": enabled, "project": project})


@tool(name="get_admin_settings", description="Read the full admin config: feature flags (global + per-project), knowledgebase settings. Budget limits live in BudgetGuardian/set_budget_limit, not here.",
      schema={"type": "object", "properties": {}})
async def _handle_get_admin_settings(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.admin_config import get_admin_settings
    return json.dumps(get_admin_settings())
