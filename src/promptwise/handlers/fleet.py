"""handlers.fleet -- agent fleet governance MCP tool handlers (WP5). New
category, no pre-split ordering to preserve -- see core/fleet.py.
"""
from __future__ import annotations

import json

from promptwise.core.tool_registry import ServerContext, tool


@tool(name="register_agent", description="Register (or update, upsert by agent_id) an AI agent operating against this repo: role, responsibilities, allowed tools, budget, owner, and OWASP NHI Top 10 credential metadata (scoped_credential flag, last_rotation_date, jit_grant_signature linking back to a grant_jit_permission signature). Set prefill_from_detect_agents=true to seed role (only) from the read-only detect_agents() repo probe instead of passing it explicitly.",
         schema={"type": "object", "properties": {
             "agent_id": {"type": "string"}, "role": {"type": "string", "default": ""},
             "responsibilities": {"type": "array", "items": {"type": "string"}, "default": []},
             "allowed_tools": {"type": "array", "items": {"type": "string"}, "default": []},
             "budget_usd": {"type": "number", "default": 0.0},
             "priority": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"},
             "owner": {"type": "string", "default": ""},
             "scoped_credential": {"type": "boolean", "default": False},
             "last_rotation_date": {"type": "string", "default": ""},
             "jit_grant_signature": {"type": "string", "default": ""},
             "prefill_from_detect_agents": {"type": "boolean", "default": False},
             "repo_root": {"type": "string", "default": "."}},
         "required": ["agent_id"]})
async def _handle_register_agent(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.fleet import FleetRegistry

    role = arguments.get("role", "")
    allowed_tools = arguments.get("allowed_tools", [])
    if arguments.get("prefill_from_detect_agents"):
        from promptwise.core.agent_detector import detect_agents
        detection = detect_agents(arguments.get("repo_root", "."))
        if detection.targets and not role:
            role = detection.targets[0]

    rec = FleetRegistry().register(
        arguments.get("agent_id", ""), role=role,
        responsibilities=arguments.get("responsibilities", []), allowed_tools=allowed_tools,
        budget_usd=float(arguments.get("budget_usd", 0.0)), priority=arguments.get("priority", "medium"),
        owner=arguments.get("owner", ""), scoped_credential=bool(arguments.get("scoped_credential", False)),
        last_rotation_date=arguments.get("last_rotation_date", ""),
        jit_grant_signature=arguments.get("jit_grant_signature", ""))
    return json.dumps(rec)


@tool(name="detect_sprawl", description="Capability-overlap report across every registered agent: tool-set Jaccard similarity for pairs above jaccard_threshold, plus role duplication (2+ agents sharing a role string). Advisory -- flags candidates for consolidation, doesn't merge anything.",
         schema={"type": "object", "properties": {"jaccard_threshold": {"type": "number", "default": 0.6}}})
async def _handle_detect_sprawl(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.fleet import FleetRegistry, detect_sprawl
    result = detect_sprawl(FleetRegistry(), jaccard_threshold=float(arguments.get("jaccard_threshold", 0.6)))
    return json.dumps(result)


@tool(name="detect_agent_drift", description="Compare a registered agent's recent audit-trail activity (rules_applied/files_touched from record_audit calls with agent=agent_id) against its registered role/allowed_tools, reusing the WP2 behavior-baseline/anomaly-detection machinery. A finding whose threat_score crosses drift_threshold auto-creates a WP3 incident (set auto_incident=false to only report). Advisory -- the OWASP 'rogue agent precursor' loop.",
         schema={"type": "object", "properties": {
             "agent_id": {"type": "string"}, "window_days": {"type": "integer", "default": 7},
             "drift_threshold": {"type": "number", "default": 60.0},
             "auto_incident": {"type": "boolean", "default": True}},
         "required": ["agent_id"]})
async def _handle_detect_agent_drift(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.fleet import FleetRegistry, detect_agent_drift
    from promptwise.core.tool_registry import _get_audit_log
    result = detect_agent_drift(
        FleetRegistry(), arguments.get("agent_id", ""), audit_log=_get_audit_log(),
        window_days=int(arguments.get("window_days", 7)),
        drift_threshold=float(arguments.get("drift_threshold", 60.0)),
        auto_incident=bool(arguments.get("auto_incident", True)))
    return json.dumps(result)


@tool(name="fleet_report", description="Per-agent rollup across every registered agent: best-effort cost attribution (from cost_logs, by tool-name overlap with allowed_tools), gate pass rate (from the audit trail), last-known drift score, and stale-credential flags (scoped_credential agents whose last_rotation_date is older than stale_credential_days, default 90). Feeds export_org_report.",
         schema={"type": "object", "properties": {"stale_credential_days": {"type": "integer", "default": 90}}})
async def _handle_fleet_report(ctx: ServerContext, arguments: dict) -> str:
    from promptwise.core.fleet import FleetRegistry, build_fleet_report
    from promptwise.core.tool_registry import _get_audit_log

    cost_logs: list[dict] = []
    try:
        from promptwise.db.models import MemoryManager, get_db_path
        cost_logs = await MemoryManager(str(get_db_path())).raw_cost_logs()
    except Exception:
        pass  # fail-soft: report still runs with cost data omitted

    result = build_fleet_report(
        FleetRegistry(), audit_log=_get_audit_log(), cost_logs=cost_logs,
        stale_credential_days=int(arguments.get("stale_credential_days", 90)))
    return json.dumps(result)
