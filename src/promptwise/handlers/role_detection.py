"""handlers.role_detection -- role detection, task tracking, and mermaid
validation MCP tool handlers (moved verbatim from server.py's "Role
Detection" section during the handlers/ package split; see
docs/superpowers/specs/2026-07-22-handlers-package-split-design.md)."""
from __future__ import annotations

import json

from promptwise.core import validate_mermaid
from promptwise.core.tool_registry import ServerContext, tool


@tool(name="plan_workflow", description="Classify a task (greenfield/brownfield/regulated) and return an ordered workflow of PromptWise's own skill packs + tools to run (PRD -> design -> stories -> TDD -> review). No third-party frameworks.",
         schema={"type": "object", "properties": {
             "text": {"type": "string"},
             "regulated": {"type": "boolean", "description": "Override auto-detection of regulated/compliance context"},
             "brownfield": {"type": "boolean", "description": "Override auto-detection of brownfield (existing-code) change"}},
         "required": ["text"]})
async def _handle_plan_workflow(ctx: ServerContext, arguments: dict) -> str:
    plan = ctx.workflow_planner.plan(
        text=arguments.get("text", ""),
        regulated=arguments.get("regulated"),
        brownfield=arguments.get("brownfield"))
    return json.dumps({"workflow": plan.workflow, "reason": plan.reason,
                       "steps": [{"phase": s.phase, "skill": s.skill, "kind": s.kind} for s in plan.steps],
                       "compliance_gate": plan.compliance_gate, "signals": plan.signals})


@tool(name="add_task", description="Create a development task with an effort estimate; tracks effort, tokens, and cost",
         schema={"type": "object", "properties": {
             "title": {"type": "string"},
             "estimate_hours": {"type": "number", "default": 0},
             "status": {"type": "string", "enum": ["todo", "in_progress", "blocked", "done"], "default": "todo"},
             "tags": {"type": "array", "items": {"type": "string"}}},
         "required": ["title"]})
async def _handle_add_task(ctx: ServerContext, arguments: dict) -> str:
    res = await ctx.task_tracker.add(
        title=arguments.get("title", ""), estimate_hours=arguments.get("estimate_hours", 0),
        status=arguments.get("status", "todo"), tags=arguments.get("tags"))
    return json.dumps(res)


@tool(name="update_task", description="Update a task's status, actual hours, tokens, or cost (set or increment)",
         schema={"type": "object", "properties": {
             "task_id": {"type": "string"},
             "status": {"type": "string", "enum": ["todo", "in_progress", "blocked", "done"]},
             "actual_hours": {"type": "number"}, "tokens": {"type": "number"}, "cost_usd": {"type": "number"},
             "add_tokens": {"type": "number"}, "add_cost": {"type": "number"}},
         "required": ["task_id"]})
async def _handle_update_task(ctx: ServerContext, arguments: dict) -> str:
    res = await ctx.task_tracker.update(
        task_id=arguments.get("task_id", ""), status=arguments.get("status"),
        actual_hours=arguments.get("actual_hours"), tokens=arguments.get("tokens"),
        cost_usd=arguments.get("cost_usd"), add_tokens=arguments.get("add_tokens"),
        add_cost=arguments.get("add_cost"))
    return json.dumps(res)


@tool(name="list_tasks", description="List tracked tasks, optionally filtered by status",
         schema={"type": "object", "properties": {
             "status": {"type": "string", "enum": ["todo", "in_progress", "blocked", "done"]}}})
async def _handle_list_tasks(ctx: ServerContext, arguments: dict) -> str:
    res = await ctx.task_tracker.list(status=arguments.get("status"))
    return json.dumps({"tasks": res, "count": len(res)})


@tool(name="task_report", description="Effort (estimate vs actual), token, and cost rollup across all tasks",
         schema={"type": "object", "properties": {}})
async def _handle_task_report(ctx: ServerContext, arguments: dict) -> str:
    return json.dumps(await ctx.task_tracker.report())


@tool(name="validate_mermaid", description="Lint Mermaid diagram source (type, bracket/quote balance) so it renders",
         schema={"type": "object", "properties": {"source": {"type": "string"}}, "required": ["source"]})
async def _handle_validate_mermaid(ctx: ServerContext, arguments: dict) -> str:
    r = validate_mermaid(arguments.get("source", ""))
    return json.dumps({"valid": r.valid, "diagram_type": r.diagram_type,
                       "errors": r.errors, "warnings": r.warnings, "node_count": r.node_count})


@tool(name="detect_role", description="Detect organizational role from prompt context",
         schema={"type": "object", "properties": {"text": {"type": "string"}, "file_type": {"type": "string"}}, "required": ["text"]})
async def _handle_detect_role(ctx: ServerContext, arguments: dict) -> str:
    r = ctx.role_detector.detect(arguments.get("text", ""), context={"file_type": arguments.get("file_type", "")})
    return json.dumps({"role": r.primary_role, "confidence": r.confidence, "keywords_matched": r.keywords_matched,
                       "secondary_roles": [{"role": s, "confidence": c} for s, c in r.secondary_roles], "rationale": r.rationale})
